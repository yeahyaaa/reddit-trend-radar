from radar.briefing import Briefing, build
from radar.history import TopicChange
from radar.models import Post


def post(title, sub="ubuntu", body=""):
    return Post(title=title, subreddit=sub, summary=body, permalink=f"/r/{sub}/1")


POSTS = [
    post("Wayland tearing on nvidia", sub="ubuntu"),
    post("How do I enable wayland?", sub="ubuntu"),
    post("Wayland session crashes", sub="linux"),
    post("Kubernetes ingress question?", sub="kubernetes"),
]


def test_a_briefing_knows_what_it_watched():
    brief = build(POSTS, ["ubuntu", "linux", "kubernetes"], "2026-09-24", [])
    assert brief.subreddits == ["ubuntu", "linux", "kubernetes"]
    assert brief.generated_on == "2026-09-24"


def test_posts_are_grouped_by_community_in_the_order_requested():
    brief = build(POSTS, ["kubernetes", "ubuntu", "linux"], "2026-09-24", [])
    assert list(brief.by_community) == ["kubernetes", "ubuntu", "linux"]
    assert len(brief.by_community["ubuntu"]) == 2


def test_a_requested_community_that_returned_nothing_is_left_out():
    brief = build(POSTS, ["ubuntu", "devops"], "2026-09-24", [])
    assert "devops" not in brief.by_community


def test_cross_community_topics_are_found():
    brief = build(POSTS, ["ubuntu", "linux", "kubernetes"], "2026-09-24", [])
    assert "wayland" in [spread.word for spread in brief.spreads]


def test_the_headline_counts_are_available_without_recomputing():
    brief = build(POSTS, ["ubuntu", "linux", "kubernetes"], "2026-09-24", [])
    assert brief.post_count == 4
    assert brief.community_count == 3


def test_a_briefing_without_history_says_so():
    brief = build(POSTS, ["ubuntu"], "2026-09-24", [])
    assert brief.has_history is False
    assert brief.changes == []


def test_a_briefing_with_history_carries_the_movers():
    changes = [TopicChange("wayland", now=3, before=0)]
    brief = build(POSTS, ["ubuntu"], "2026-09-24", changes)
    assert brief.has_history is True
    assert brief.risers[0].word == "wayland"


def test_risers_and_faders_are_separated():
    changes = [
        TopicChange("wayland", now=5, before=1),
        TopicChange("snap", now=0, before=4),
        TopicChange("apt", now=2, before=2),
    ]
    brief = build(POSTS, ["ubuntu"], "2026-09-24", changes)
    assert [c.word for c in brief.risers] == ["wayland"]
    assert [c.word for c in brief.faders] == ["snap"]


def test_an_empty_run_still_builds_a_briefing():
    brief = build([], ["ubuntu"], "2026-09-24", [])
    assert isinstance(brief, Briefing)
    assert brief.post_count == 0
    assert brief.by_community == {}


MANY = [Post(title=f"post {i}", subreddit="ubuntu", permalink=f"/r/u/{i}") for i in range(30)]


def test_each_community_is_capped_separately():
    """The cap is per community: twenty from each, not twenty shared between them."""
    posts = MANY + [Post(title="elsewhere", subreddit="linux", permalink="/r/l/1")]
    brief = build(posts, ["ubuntu", "linux"], "2026-09-24", [], per_community=20)
    assert len(brief.by_community["ubuntu"]) == 20
    assert len(brief.by_community["linux"]) == 1


def test_reddits_own_order_is_kept_rather_than_re_ranked():
    """Reddit already sorted by score; re-sorting would throw that away."""
    brief = build(MANY, ["ubuntu"], "2026-09-24", [], per_community=5)
    assert [p.title for p in brief.by_community["ubuntu"]] == [f"post {i}" for i in range(5)]


def test_the_post_count_reflects_what_was_kept():
    brief = build(MANY, ["ubuntu"], "2026-09-24", [], per_community=5)
    assert brief.post_count == 5
