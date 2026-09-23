"""Rendering a ranked post list into something a human reads or a sheet opens."""

from __future__ import annotations

import csv
from pathlib import Path

from radar.models import Post

CSV_FIELDS = ["subreddit", "title", "score", "num_comments", "engagement", "url"]


def to_markdown(ranked: list[Post], keywords: list[tuple[str, int]], generated_on: str) -> str:
    """Render the daily radar as Markdown."""
    lines = [f"# Reddit Trend Radar - {generated_on}", ""]
    lines.extend(_keyword_block(keywords))
    lines.extend(["## Top posts", ""])
    if not ranked:
        lines.append("No posts matched the filters today.")
        return "\n".join(lines) + "\n"
    lines.extend(_source_note(ranked))
    lines.extend(_post_line(i, p) for i, p in enumerate(ranked, start=1))
    return "\n".join(lines) + "\n"


def write_csv(ranked: list[Post], path: str | Path) -> None:
    """Write the ranked posts to a CSV that opens cleanly in a spreadsheet."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(post.as_row() for post in ranked)


def _source_note(ranked: list[Post]) -> list[str]:
    """Say so when the numbers are missing because the Atom fallback was used."""
    if not any(post.source == "rss" for post in ranked):
        return []
    return [
        "_Some entries came from the Atom feed, which carries no score or comment "
        "count. Those keep Reddit's own ordering._",
        "",
    ]


def _keyword_block(keywords: list[tuple[str, int]]) -> list[str]:
    if not keywords:
        return []
    rendered = ", ".join(f"{word} ({count})" for word, count in keywords)
    return ["## Trending words", "", rendered, ""]


def _post_line(index: int, post: Post) -> str:
    return f"{index}. [{post.title}]({post.link}) - r/{post.subreddit} - {_stats(post)}"


def _stats(post: Post) -> str:
    """Render the metrics, or say they are absent on the Atom path."""
    if not post.has_metrics:
        return "metrics unavailable"
    return f"{int(post.score or 0)} pts, {int(post.num_comments or 0)} comments"
