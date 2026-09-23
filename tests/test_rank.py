from radar.models import Post
from radar.rank import engagement_score, rank_posts


def post(score=0, comments=0, ratio=1.0, title="t", sub="ubuntu"):
    return Post(
        title=title,
        subreddit=sub,
        score=score,
        num_comments=comments,
        upvote_ratio=ratio,
        permalink="/r/x/1",
        url="https://example.test/x",
    )


def test_score_rewards_comments_more_than_upvotes():
    chatty = engagement_score(post(score=100, comments=50))
    quiet = engagement_score(post(score=150, comments=0))
    assert chatty > quiet


def test_score_penalises_contested_posts():
    agreed = engagement_score(post(score=100, comments=10, ratio=0.98))
    contested = engagement_score(post(score=100, comments=10, ratio=0.55))
    assert agreed > contested


def test_score_is_never_negative():
    assert engagement_score(post(score=-40, comments=0, ratio=0.1)) >= 0


def test_a_post_with_no_metrics_scores_zero():
    assert engagement_score(Post(title="bare", subreddit="ubuntu")) == 0.0


def test_rank_sorts_descending_and_truncates():
    posts = [
        post(score=10, title="low"),
        post(score=900, title="high"),
        post(score=50, title="mid"),
    ]
    ranked = rank_posts(posts, 2)
    assert [p.title for p in ranked] == ["high", "mid"]


def test_rank_attaches_the_score_to_each_post():
    ranked = rank_posts([post(score=10, comments=2)], 5)
    assert ranked[0].engagement > 0


def test_rank_keeps_reddit_order_when_nothing_can_be_scored():
    """Every Atom-sourced post scores zero, so the sort must be stable."""
    feed_order = [
        Post(title="first", subreddit="ubuntu", source="rss"),
        Post(title="second", subreddit="ubuntu", source="rss"),
        Post(title="third", subreddit="ubuntu", source="rss"),
    ]
    assert [p.title for p in rank_posts(feed_order, 3)] == ["first", "second", "third"]


def test_rank_handles_empty_input():
    assert rank_posts([], 5) == []
