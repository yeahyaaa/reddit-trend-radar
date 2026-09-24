"""Everything one run has to say, assembled once and rendered many times.

The Markdown, LaTeX and spreadsheet outputs used to each work out their own view
of the data. They now share this, so a change to what the briefing contains lands
in every format at once and they cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from radar.ai import Story
from radar.analysis import TopicSpread, cross_community, topic_counts
from radar.history import TopicChange
from radar.models import Post


@dataclass(slots=True)
class Briefing:
    """One run, read for meaning rather than as a list of posts."""

    generated_on: str
    subreddits: list[str]
    posts: list[Post]
    by_community: dict[str, list[Post]]
    topics: list[tuple[str, int]]
    spreads: list[TopicSpread]
    changes: list[TopicChange] = field(default_factory=list)
    stories: list[Story] = field(default_factory=list)

    @property
    def post_count(self) -> int:
        return len(self.posts)

    @property
    def community_count(self) -> int:
        return len(self.by_community)

    @property
    def has_stories(self) -> bool:
        """False unless a model was configured and had something to say."""
        return bool(self.stories)

    @property
    def has_history(self) -> bool:
        """False on a first run, when there is nothing to compare against."""
        return bool(self.changes)

    @property
    def risers(self) -> list[TopicChange]:
        return [c for c in self.changes if c.status in ("new", "rising")]

    @property
    def faders(self) -> list[TopicChange]:
        return [c for c in self.changes if c.status in ("gone", "falling")]


def build(
    posts: list[Post],
    subreddits: list[str],
    generated_on: str,
    changes: list[TopicChange] | None = None,
    per_community: int = 20,
    stories: list[Story] | None = None,
) -> Briefing:
    """Read a run's posts into the shape every output format renders from."""
    grouped = _group(posts, subreddits, per_community)
    kept = [post for group in grouped.values() for post in group]
    return Briefing(
        generated_on=generated_on,
        subreddits=subreddits,
        posts=kept,
        by_community=grouped,
        topics=topic_counts(kept, 15),
        spreads=cross_community(kept),
        changes=changes or [],
        stories=stories or [],
    )


def _group(posts: list[Post], subreddits: list[str], cap: int) -> dict[str, list[Post]]:
    """The first `cap` posts of each community, in the order Reddit returned them.

    Reddit's top listing is already sorted by score. Re-sorting it here would
    replace that with a guess, so the order is left alone and only trimmed.
    """
    grouped: dict[str, list[Post]] = {}
    for name in subreddits:
        found = [p for p in posts if p.subreddit.lower() == name.lower()][:cap]
        if found:
            grouped[name] = found
    return grouped
