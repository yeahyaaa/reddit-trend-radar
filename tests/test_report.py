import csv

from radar.models import Post
from radar.report import to_markdown, write_csv

RANKED = [
    Post(
        title="Ubuntu 26.04 released",
        subreddit="ubuntu",
        score=900,
        num_comments=120,
        engagement=1140.0,
        permalink="/r/ubuntu/comments/1",
    )
]

RSS_POST = Post(
    title="Snap vs flatpak",
    subreddit="ubuntu",
    permalink="/r/ubuntu/comments/2",
    source="rss",
)


def test_markdown_contains_title_and_subreddit():
    out = to_markdown(RANKED, [("ubuntu", 3)], "2026-09-24")
    assert "Ubuntu 26.04 released" in out
    assert "r/ubuntu" in out


def test_markdown_links_are_absolute():
    assert "https://www.reddit.com/r/ubuntu/comments/1" in to_markdown(RANKED, [], "2026-09-24")


def test_markdown_lists_keywords():
    assert "kubernetes" in to_markdown(RANKED, [("kubernetes", 4)], "2026-09-24")


def test_markdown_shows_the_metrics_when_there_are_some():
    assert "900 pts, 120 comments" in to_markdown(RANKED, [], "2026-09-24")


def test_markdown_renders_posts_with_no_metrics():
    out = to_markdown([RSS_POST], [], "2026-09-24")
    assert "Snap vs flatpak" in out
    assert "None" not in out


def test_markdown_flags_the_atom_fallback():
    assert "Atom feed" in to_markdown([RSS_POST], [], "2026-09-24")


def test_markdown_omits_the_fallback_note_for_json_posts():
    assert "Atom feed" not in to_markdown(RANKED, [], "2026-09-24")


def test_markdown_handles_no_posts():
    assert "No posts" in to_markdown([], [], "2026-09-24")


def test_csv_writes_one_row_per_post(tmp_path):
    target = tmp_path / "out.csv"
    write_csv(RANKED, target)
    with open(target, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["subreddit"] == "ubuntu"
    assert rows[0]["score"] == "900"


def test_csv_leaves_missing_metrics_blank(tmp_path):
    target = tmp_path / "rss.csv"
    write_csv([RSS_POST], target)
    with open(target, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["title"] == "Snap vs flatpak"
    assert rows[0]["score"] == ""
