"""A record of past runs, which is what turns a snapshot into a trend.

Without this the tool tells you what Reddit's own front page already tells you.
With it you can say which topics are new this week, which are growing, and which
have gone quiet — none of which Reddit shows anywhere.

One SQLite file, created on first use. Nothing leaves your machine.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from radar.analysis import topic_words
from radar.models import Post

DEFAULT_PATH = Path("radar-history.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    ran_on     TEXT PRIMARY KEY,
    subreddits TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    ran_on    TEXT NOT NULL REFERENCES runs(ran_on) ON DELETE CASCADE,
    subreddit TEXT NOT NULL,
    title     TEXT NOT NULL,
    permalink TEXT,
    author    TEXT,
    published TEXT,
    score     INTEGER,
    comments  INTEGER,
    body      TEXT
);
CREATE INDEX IF NOT EXISTS posts_by_run ON posts(ran_on);
"""


@dataclass(slots=True)
class Run:
    ran_on: str
    subreddits: list[str]
    post_count: int


@dataclass(slots=True)
class TopicChange:
    """One topic, then and now."""

    word: str
    now: int
    before: int

    @property
    def delta(self) -> int:
        return self.now - self.before

    @property
    def status(self) -> str:
        if self.before == 0:
            return "new"
        if self.now == 0:
            return "gone"
        if self.now > self.before:
            return "rising"
        if self.now < self.before:
            return "falling"
        return "steady"


@contextmanager
def open_store(path: str | Path = DEFAULT_PATH) -> Iterator[sqlite3.Connection]:
    """Open the history file, creating it and its tables if this is the first run."""
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def record_run(
    connection: sqlite3.Connection, posts: list[Post], subreddits: list[str], ran_on: str
) -> None:
    """Store this run, replacing any earlier run from the same day.

    Replacing rather than appending means running the tool twice in an afternoon
    does not read as the topic having doubled overnight.
    """
    connection.execute("DELETE FROM posts WHERE ran_on = ?", (ran_on,))
    connection.execute("DELETE FROM runs WHERE ran_on = ?", (ran_on,))
    connection.execute("INSERT INTO runs VALUES (?, ?)", (ran_on, ",".join(subreddits)))
    connection.executemany(
        "INSERT INTO posts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                ran_on, p.subreddit, p.title, p.permalink,
                p.author, p.published, p.score, p.num_comments, p.summary,
            )
            for p in posts
        ],
    )


def recent_runs(connection: sqlite3.Connection, limit: int = 14) -> list[Run]:
    """The most recent runs, newest first."""
    rows = connection.execute(
        """SELECT r.ran_on, r.subreddits, COUNT(p.rowid)
           FROM runs r LEFT JOIN posts p ON p.ran_on = r.ran_on
           GROUP BY r.ran_on ORDER BY r.ran_on DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [Run(ran_on, subs.split(",") if subs else [], count) for ran_on, subs, count in rows]


def compare_runs(connection: sqlite3.Connection, top_n: int = 15) -> list[TopicChange]:
    """How the latest run's topics differ from the run before it.

    Empty on a first run, which is the honest answer rather than calling every
    topic brand new.
    """
    days = [run.ran_on for run in recent_runs(connection, 2)]
    if len(days) < 2:
        return []
    now, before = _counts_for(connection, days[0]), _counts_for(connection, days[1])
    changes = [
        TopicChange(word, now.get(word, 0), before.get(word, 0))
        for word in set(now) | set(before)
    ]
    changes.sort(key=lambda c: (abs(c.delta), c.now), reverse=True)
    return changes[:top_n]


def topic_series(
    connection: sqlite3.Connection, word: str, limit: int = 14
) -> list[tuple[str, int]]:
    """One topic's count on each recorded day, oldest first, zeroes included."""
    days = [run.ran_on for run in recent_runs(connection, limit)][::-1]
    return [(day, _counts_for(connection, day).get(word, 0)) for day in days]


def _counts_for(connection: sqlite3.Connection, ran_on: str) -> Counter[str]:
    """How many posts mentioned each topic on one day."""
    rows = connection.execute(
        "SELECT title, body FROM posts WHERE ran_on = ?", (ran_on,)
    ).fetchall()
    counter: Counter[str] = Counter()
    for title, body in rows:
        counter.update(topic_words(Post(title=title, subreddit="", summary=body or "")))
    return counter
