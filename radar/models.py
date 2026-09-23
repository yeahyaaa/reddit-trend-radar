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
    source: str = "json"
    engagement: float = field(default=0.0, compare=False)

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
            "title": self.title,
            "score": "" if self.score is None else self.score,
            "num_comments": "" if self.num_comments is None else self.num_comments,
            "engagement": round(self.engagement, 2),
            "url": self.link,
        }
