"""Scoring and ordering of fetched posts.

A post people argue about is worth more to a content calendar than a post people
silently upvote, so comments weigh heavier than score. Contested posts, meaning a
low upvote ratio, are damped, because they usually signal a fight rather than a
topic.
"""

from __future__ import annotations

from radar.models import Post

COMMENT_WEIGHT = 3.0


def engagement_score(post: Post) -> float:
    """A single comparable number for one post, never negative."""
    score = float(post.score or 0)
    comments = float(post.num_comments or 0)
    ratio = 1.0 if post.upvote_ratio is None else float(post.upvote_ratio)
    return max((score + comments * COMMENT_WEIGHT) * ratio, 0.0)


def rank_posts(posts: list[Post], top_n: int) -> list[Post]:
    """Score every post and return the best ones first.

    The sort is stable, so posts that scored equally, which is every post when the
    Atom fallback supplied them, keep the order Reddit gave them.
    """
    for post in posts:
        post.engagement = engagement_score(post)
    return sorted(posts, key=lambda p: p.engagement, reverse=True)[:top_n]
