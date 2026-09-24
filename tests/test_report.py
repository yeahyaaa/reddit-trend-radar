import csv

from radar.briefing import build
from radar.history import TopicChange
from radar.models import Post
from radar.report import to_markdown, write_csv

WITH_METRICS = Post(
    title="Ubuntu 26.04 released",
    subreddit="ubuntu",
    score=900,
    num_comments=120,
    permalink="/r/ubuntu/comments/1",
    author="someone",
    published="2026-09-23T11:23:09+00:00",
)

NO_METRICS = Post(
    title="Wayland session crashes",
    subreddit="ubuntu",
    permalink="/r/ubuntu/comments/2",
    summary="It dies whenever I unplug the monitor.",
    source="rss",
)

LINK_POST = Post(
    title="Hurricane Polo hits Category 5",
    subreddit="news",
    permalink="/r/news/comments/3",
    source_url="https://www.cnn.com/2026/09/22/weather/hurricane-polo",
    source="rss",
)

ELSEWHERE = Post(title="Wayland tearing", subreddit="linux", permalink="/r/linux/comments/4")
ALSO = Post(title="Wayland stutter", subreddit="linux", permalink="/r/linux/comments/5")

DEFAULT = [WITH_METRICS, NO_METRICS, LINK_POST, ELSEWHERE, ALSO]


def brief(posts=None, subs=None, changes=None):
    return build(
        DEFAULT if posts is None else posts,
        subs or ["ubuntu", "news", "linux"],
        "2026-09-24",
        changes or [],
    )


class TestStructure:
    def test_the_watched_communities_are_named(self):
        assert "Watching r/ubuntu, r/news, r/linux" in to_markdown(brief())

    def test_the_summary_says_how_many_came_from_where(self):
        out = to_markdown(brief())
        assert "5 posts" in out
        assert "r/ubuntu 2" in out

    def test_each_community_gets_its_own_section(self):
        out = to_markdown(brief())
        for heading in ("## r/ubuntu", "## r/news", "## r/linux"):
            assert heading in out

    def test_posts_come_before_the_cross_community_table(self):
        """The posts are the point; the analysis is a footnote to them."""
        # Padding keeps the document-frequency ceiling from pruning wayland, which
        # is in three of five posts without it and so looks too common to mention.
        padding = [
            Post(title=f"unrelated chatter {i}", subreddit="ubuntu", permalink=f"/r/u/{i}")
            for i in range(10)
        ]
        out = to_markdown(brief(posts=DEFAULT + padding))
        assert out.index("## r/ubuntu") < out.index("Words appearing in more than one")

    def test_an_empty_run_still_renders(self):
        assert "0 posts" in to_markdown(brief(posts=[], subs=["ubuntu"]))


class TestPosts:
    def test_posts_are_numbered_within_their_community(self):
        out = to_markdown(brief())
        assert "**1. Ubuntu 26.04 released**" in out
        assert "**2. Wayland session crashes**" in out

    def test_every_post_links_to_its_discussion(self):
        assert "[Discussion](https://www.reddit.com/r/ubuntu/comments/1)" in to_markdown(brief())

    def test_a_link_post_also_links_to_the_article(self):
        expected = "[Source](https://www.cnn.com/2026/09/22/weather/hurricane-polo)"
        assert expected in to_markdown(brief())

    def test_a_self_post_has_no_source_link(self):
        out = to_markdown(brief(posts=[NO_METRICS], subs=["ubuntu"]))
        assert "[Source]" not in out

    def test_the_score_is_shown_when_reddit_gave_one(self):
        assert "900 points, 120 comments" in to_markdown(brief())

    def test_a_post_with_no_score_says_nothing_rather_than_apologising(self):
        out = to_markdown(brief(posts=[NO_METRICS], subs=["ubuntu"]))
        assert "metrics unavailable" not in out
        assert "Wayland session crashes" in out

    def test_the_body_is_quoted_under_the_post(self):
        assert "> It dies whenever I unplug the monitor." in to_markdown(brief())


class TestHistory:
    def test_a_first_run_says_it_has_no_comparison(self):
        assert "First run" in to_markdown(brief())

    def test_a_later_run_reports_what_changed(self):
        out = to_markdown(brief(changes=[TopicChange("wayland", now=5, before=1)]))
        assert "What changed since the last run" in out
        assert "rising, 1 to 5" in out


class TestCsv:
    def test_one_row_per_post(self, tmp_path):
        target = tmp_path / "out.csv"
        write_csv([WITH_METRICS], target)
        with open(target, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1
        assert rows[0]["score"] == "900"

    def test_missing_metrics_are_left_blank(self, tmp_path):
        target = tmp_path / "rss.csv"
        write_csv([NO_METRICS], target)
        with open(target, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["score"] == ""


class TestStories:
    def story(self):
        from radar.ai import Story

        return Story(
            headline="Hurricane Polo reaches Category 5",
            summary="Both communities covered the storm intensifying overnight.",
            posts=[LINK_POST, ELSEWHERE],
        )

    def brief_with_story(self):
        return build(DEFAULT, ["ubuntu", "news", "linux"], "2026-09-24", [], 20, [self.story()])

    def test_the_section_is_absent_without_a_model(self):
        assert "What these communities are talking about" not in to_markdown(brief())

    def test_the_headline_and_summary_appear(self):
        out = to_markdown(self.brief_with_story())
        assert "Hurricane Polo reaches Category 5" in out
        assert "covered the storm intensifying" in out

    def test_it_says_how_many_posts_and_where(self):
        assert "2 posts across r/news, r/linux" in to_markdown(self.brief_with_story())

    def test_each_grouped_post_is_linked(self):
        out = to_markdown(self.brief_with_story())
        assert "https://www.reddit.com/r/news/comments/3" in out

    def test_the_section_says_the_grouping_was_generated(self):
        """A reader should never be unsure which parts a model wrote."""
        out = to_markdown(self.brief_with_story())
        assert "language model" in out

    def test_it_says_the_links_were_not_the_models(self):
        assert "never URLs" in to_markdown(self.brief_with_story())
