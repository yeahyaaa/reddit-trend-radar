"""The briefing as Markdown, and the posts as CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from radar.briefing import Briefing
from radar.models import Post

CSV_FIELDS = [
    "subreddit", "posted", "author", "title", "body",
    "score", "num_comments", "url", "source_url",
]


def to_markdown(brief: Briefing) -> str:
    """Render the whole briefing as Markdown."""
    watched = ", ".join(f"r/{name}" for name in brief.subreddits)
    lines = [f"# Reddit Trend Radar - {brief.generated_on}", "", f"Watching {watched}.", ""]
    lines += _summary(brief) + _stories(brief) + _communities(brief)
    lines += _changes(brief) + _spreads(brief)
    return "\n".join(lines).rstrip() + "\n"


def write_csv(ranked: list[Post], path: str | Path) -> None:
    """Write the posts to a CSV that opens cleanly in a spreadsheet."""
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(post.as_row() for post in ranked)


def _summary(brief: Briefing) -> list[str]:
    counts = ", ".join(f"r/{n} {len(p)}" for n, p in brief.by_community.items())
    lines = [
        f"Top posts of the period, in Reddit's own ranking. {brief.post_count} posts: {counts}.",
    ]
    if not brief.has_history:
        lines.append("")
        lines.append("_First run: nothing to compare against yet._")
    return [*lines, ""]


def _stories(brief: Briefing) -> list[str]:
    """What the model made of the run, clearly labelled as its reading and not ours."""
    if not brief.has_stories:
        return []
    lines = [
        "## What these communities are talking about",
        "",
        "_Grouped by a language model from the posts below. The links are ours, not its:_",
        "_it was shown post numbers, never URLs._",
        "",
    ]
    for story in brief.stories:
        where = ", ".join(f"r/{name}" for name in story.subreddits)
        lines.append(f"**{story.headline}**  ")
        lines.append(f"{_count(len(story.posts))} across {where}")
        if story.summary:
            lines += ["", story.summary]
        lines += ["", *[f"- [{p.title}]({p.link})" for p in story.posts], ""]
    return lines


def _count(number: int) -> str:
    """One post, two posts. A grammar slip here reads as carelessness everywhere else."""
    return f"{number} post" if number == 1 else f"{number} posts"


def _communities(brief: Briefing) -> list[str]:
    lines: list[str] = []
    for name, posts in brief.by_community.items():
        lines += [f"## r/{name}", ""]
        for index, post in enumerate(posts, start=1):
            lines += _post_block(index, post)
        lines.append("")
    return lines


def _post_block(index: int, post: Post) -> list[str]:
    """Title, where it came from, both links, and whatever the author wrote."""
    lines = [f"**{index}. {post.title}**", ""]
    if _meta(post):
        lines.append(f"{_meta(post)}  ")
    links = f"[Discussion]({post.link})"
    if post.source_url:
        links += f" - [Source]({post.source_url})"
    lines.append(links)
    if post.summary:
        lines += ["", f"> {post.summary}"]
    return [*lines, ""]


def _meta(post: Post) -> str:
    """Author, time and score, each skipped when this transport did not carry it."""
    bits = [f"u/{post.author}"] if post.author else []
    if post.posted_at:
        bits.append(post.posted_at)
    if post.has_metrics:
        bits.append(f"{int(post.score or 0)} points, {int(post.num_comments or 0)} comments")
    return " - ".join(bits)


def _changes(brief: Briefing) -> list[str]:
    if not brief.has_history:
        return []
    moved = (brief.risers + brief.faders)[:12]
    items = [f"- **{c.word}** - {c.status}, {c.before} to {c.now}" for c in moved]
    return ["## What changed since the last run", "", *items, ""]


def _spreads(brief: Briefing) -> list[str]:
    if not brief.spreads:
        return []
    names = list(brief.by_community)
    head = "| Topic | " + " | ".join(f"r/{n}" for n in names) + " |"
    rule = "| --- |" + " --- |" * len(names)
    rows = [
        "| " + " | ".join([s.word] + [str(s.counts.get(n, "") or "") for n in names]) + " |"
        for s in brief.spreads
    ]
    return [
        "## Words appearing in more than one community",
        "",
        "_Counted, not read. The section above does this properly when a model is configured._",
        "",
        head,
        rule,
        *rows,
        "",
    ]
