from radar.briefing import build
from radar.history import TopicChange
from radar.latex import to_latex
from radar.models import Post

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
    summary="It dies with 100% CPU whenever I unplug the monitor & replug it.",
)

LINK_POST = Post(
    title="Hurricane Polo hits Category 5",
    subreddit="news",
    permalink="/r/news/comments/3",
    source_url="https://www.cnn.com/2026/09/22/weather/hurricane-polo",
)

ELSEWHERE = Post(title="Wayland tearing", subreddit="linux", permalink="/r/linux/comments/4")
ALSO = Post(title="Wayland stutter", subreddit="linux", permalink="/r/linux/comments/5")

DEFAULT = [WITH_METRICS, NO_METRICS, LINK_POST, ELSEWHERE, ALSO]


def brief(posts=None, changes=None):
    return build(
        DEFAULT if posts is None else posts,
        ["ubuntu", "news", "linux"],
        "2026-09-24",
        changes or [],
    )


class TestDocument:
    def test_it_is_self_contained(self):
        out = to_latex(brief())
        assert out.startswith(r"\documentclass")
        assert out.rstrip().endswith(r"\end{document}")

    def test_the_watched_communities_are_named_at_the_top(self):
        assert "Watching r/ubuntu, r/news, r/linux" in to_latex(brief())

    def test_the_date_is_present(self):
        assert "2026-09-24" in to_latex(brief())

    def test_optional_packages_are_guarded(self):
        """A minimal LaTeX install must still compile this."""
        for package in ("libertinus", "microtype", "booktabs", "fancyhdr", "titlesec"):
            assert rf"\IfFileExists{{{package}.sty}}" in to_latex(brief())


class TestStructure:
    def test_the_summary_says_how_many_came_from_where(self):
        out = to_latex(brief())
        assert "5 posts" in out
        assert "r/ubuntu~2" in out

    def test_each_community_gets_a_heading_with_its_count(self):
        out = to_latex(brief())
        assert r"r/ubuntu \normalsize(2 posts)" in out
        assert r"r/linux \normalsize(2 posts)" in out

    def test_posts_come_before_the_cross_community_table(self):
        """The posts are the point; the analysis is a footnote to them."""
        padding = [
            Post(title=f"unrelated chatter {i}", subreddit="ubuntu", permalink=f"/r/u/{i}")
            for i in range(10)
        ]
        out = to_latex(brief(posts=DEFAULT + padding))
        assert out.index(r"\section*{r/ubuntu") < out.index("Words appearing in more than one")

    def test_a_first_run_says_it_has_no_comparison(self):
        assert "First run" in to_latex(brief())

    def test_a_later_run_reports_what_changed(self):
        out = to_latex(brief(changes=[TopicChange("wayland", now=5, before=1)]))
        assert "What changed since the last run" in out
        assert "First run" not in out


class TestPosts:
    def test_every_post_links_to_its_discussion(self):
        assert r"\href{https://www.reddit.com/r/ubuntu/comments/1}{Discussion}" in to_latex(brief())

    def test_a_link_post_also_links_to_the_article(self):
        expected = r"\href{https://www.cnn.com/2026/09/22/weather/hurricane-polo}{Source}"
        assert expected in to_latex(brief())

    def test_a_self_post_has_no_source_link(self):
        assert "{Source}" not in to_latex(brief(posts=[NO_METRICS]))

    def test_the_score_is_shown_when_reddit_gave_one(self):
        assert "900 points, 120 comments" in to_latex(brief())

    def test_a_post_with_no_score_says_nothing_rather_than_apologising(self):
        out = to_latex(brief(posts=[NO_METRICS]))
        assert "metrics unavailable" not in out
        assert "Wayland session crashes" in out

    def test_the_author_and_time_are_shown(self):
        out = to_latex(brief())
        assert "u/someone" in out
        assert "2026-09-23 11:23" in out

    def test_the_body_is_kept_in_full(self):
        wordy = Post(title="t", subreddit="ubuntu", permalink="/r/x/1", summary="word " * 300)
        out = to_latex(brief(posts=[wordy]))
        assert out.count("word") >= 300
        assert "..." not in out

    def test_a_hostile_body_is_escaped(self):
        assert r"100\% CPU" in to_latex(brief())

    def test_font_switches_are_scoped_so_they_cannot_leak(self):
        out = to_latex(brief())
        for switch in (r"\itshape", r"\small"):
            for i in (j for j in range(len(out)) if out.startswith(switch, j)):
                prefix = out[:i].replace(r"\{", "").replace(r"\}", "")
                assert prefix.count("{") > prefix.count("}"), f"{switch} is not grouped"


class TestTableLayout:
    def test_the_caption_ends_its_paragraph_before_the_table(self):
        """Without the break the caption renders beside the table instead of above it."""
        padding = [
            Post(title=f"unrelated chatter {i}", subreddit="ubuntu", permalink=f"/r/u/{i}")
            for i in range(10)
        ]
        out = to_latex(brief(posts=DEFAULT + padding))
        caption = next(line for line in out.splitlines() if "Counted, not read" in line)
        assert caption.rstrip().endswith(r"\par")

    def test_rules_are_macros_not_inline_conditionals(self):
        r"""\toprule expands to \noalign and cannot sit inside a conditional in a table."""
        out = to_latex(brief())
        assert r"\newcommand{\radartop}" in out
        assert r"\IfFileExists{booktabs.sty}{\toprule}" not in out
