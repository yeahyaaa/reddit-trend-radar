"""Keyword extraction across post titles, to spot a topic before it peaks."""

from __future__ import annotations

import re
from collections import Counter

from radar.models import Post

MIN_TOKEN_LENGTH = 2

_STOPWORD_TEXT = """
    a an the of in on at to for with from by and or but if is are was were be been being
    this that these those it its as not no can could would should will just my your our
    their his her how what when where why who which do does did have has had get got
    any all some more most much very really new one two use used using
"""

STOPWORDS = frozenset(_STOPWORD_TEXT.split())

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str | None) -> list[str]:
    """Lowercase a title and return its meaningful words."""
    if not isinstance(text, str):
        return []
    words = _WORD.findall(text.lower())
    return [w for w in words if len(w) >= MIN_TOKEN_LENGTH and w not in STOPWORDS]


def extract_keywords(posts: list[Post], top_n: int) -> list[tuple[str, int]]:
    """The most frequent words across all titles, commonest first."""
    counter: Counter[str] = Counter()
    for post in posts:
        counter.update(tokenize(post.title))
    return counter.most_common(top_n)
