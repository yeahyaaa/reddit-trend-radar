"""What the posts add up to, once you stop looking at them one at a time.

Two readings, none of which Reddit shows you anywhere:

  topic_counts    what is being talked about at all
  cross_community which of those topics turned up in more than one community,
                  which is the difference between one person's bad day and a
                  thing that is actually going around
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from radar.keywords import tokenize
from radar.models import Post
from radar.stopwords import STOPWORDS

# A word in most of the posts is true but useless: reading r/ubuntu, "ubuntu" is in
# everything and distinguishes nothing. Drop anything above this share of posts.
DOCUMENT_FREQUENCY_CEILING = 0.4

# Below this the corpus is too small for the ceiling to mean anything, and applying
# it would empty the report.
CEILING_APPLIES_FROM = 5

# Appearing once in each of three communities is coincidence. Ask for a real count
# before calling something a shared topic.
MINIMUM_MENTIONS = 3

_NUMERIC = re.compile(r"^\d+$")


@dataclass(slots=True)
class TopicSpread:
    """One topic and how it is distributed across the communities watched."""

    word: str
    counts: dict[str, int]

    @property
    def communities(self) -> int:
        return len(self.counts)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def topic_words(post: Post) -> set[str]:
    """The distinct topic words in one post, title and body together.

    A set, not a list: counting every repetition lets a single rambling post
    decide what the whole briefing is about.
    """
    words = tokenize(post.title) + tokenize(post.summary)
    return {word for word in words if _is_topical(word)}


def topic_counts(posts: list[Post], top_n: int = 20) -> list[tuple[str, int]]:
    """How many posts mention each topic, commonest first."""
    return Counter(_pruned_words(posts)).most_common(top_n)


def cross_community(posts: list[Post], top_n: int = 12) -> list[TopicSpread]:
    """Topics that showed up in more than one community, widest spread first."""
    keep = set(_pruned_words(posts))
    per_word: dict[str, Counter[str]] = {}
    for post in posts:
        for word in topic_words(post) & keep:
            per_word.setdefault(word, Counter())[post.subreddit] += 1
    spreads = [TopicSpread(word, dict(counts)) for word, counts in per_word.items()]
    shared = [
        spread
        for spread in spreads
        if spread.communities > 1 and spread.total >= MINIMUM_MENTIONS
    ]
    # Total first: a word said nine times across two communities is a bigger story
    # than one said once each in three, which is usually just coincidence.
    shared.sort(key=lambda s: (s.total, s.communities), reverse=True)
    return shared[:top_n]


def _is_topical(word: str) -> bool:
    """A word that could name a subject: not filler, not a bare version number."""
    return len(word) > 2 and word not in STOPWORDS and not _NUMERIC.match(word)


def _pruned_words(posts: list[Post]) -> list[str]:
    """Every post's topic words, minus the ones that turn up in most of them."""
    words = [word for post in posts for word in topic_words(post)]
    if len(posts) < CEILING_APPLIES_FROM:
        return words
    ceiling = len(posts) * DOCUMENT_FREQUENCY_CEILING
    frequency = Counter(words)
    return [word for word in words if frequency[word] <= ceiling]
