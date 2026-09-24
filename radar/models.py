"""The one shape every stage of the pipeline passes along."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Post:
    """A Reddit post, as much of one as the transport we used could tell us.

    The JSON listing fills everything. The Atom feed fills the title and the link
    and leaves the counts as None, which is why they are optional rather than
    defaulted to zero: a missing score and a score of zero mean different things.
    """

    title: str
    subreddit: str
    permalink: str = ""
    url: str = ""
    score: int | None = None
    num_comments: int | None = None
    upvote_ratio: float | None = None
    author: str = ""
    published: str = ""
    summary: str = ""
    source_url: str = ""
    source: str = "json"

    @property
    def posted_at(self) -> str:
        """The timestamp trimmed to minutes, which is all anyone reads it to."""
        return self.published[:16].replace("T", " ") if self.published else ""

    @property
    def has_metrics(self) -> bool:
        """False when the transport gave us no numbers to rank on."""
        return self.score is not None or self.num_comments is not None

    @property
    def link(self) -> str:
        return f"https://www.reddit.com{self.permalink}" if self.permalink else self.url

    def as_row(self) -> dict[str, Any]:
        """Flatten to the columns the CSV exports, blanking metrics we never got."""
        return {
            "subreddit": self.subreddit,
            "posted": self.posted_at,
            "author": self.author,
            "title": self.title,
            "body": self.summary,
            "score": "" if self.score is None else self.score,
            "num_comments": "" if self.num_comments is None else self.num_comments,
            "url": self.link,
            "source_url": self.source_url,
        }


@dataclass(slots=True)
class SubredditResult:
    """What one subreddit gave us, so a run can report itself as it goes."""

    subreddit: str
    posts: list[Post] = field(default_factory=list)
    error: str | None = None
    source: str = "json"

    @property
    def ok(self) -> bool:
        return self.error is None
