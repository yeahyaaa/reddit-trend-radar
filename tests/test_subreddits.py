import pytest

from radar.subreddits import normalise, normalise_all


@pytest.mark.parametrize(
    "given",
    [
        "news",
        "r/news",
        "/r/news",
        "reddit.com/r/news",
        "https://www.reddit.com/r/news",
        "https://www.reddit.com/r/news/",
        "https://old.reddit.com/r/news/top/?t=week",
        "https://www.reddit.com/r/news/comments/abc/some_post/",
    ],
)
def test_every_way_of_naming_a_subreddit_resolves_to_its_name(given):
    assert normalise(given) == "news"


def test_case_is_preserved_as_typed():
    """Reddit does not care, but r/AskReddit reads better than r/askreddit."""
    assert normalise("AskReddit") == "AskReddit"
    assert normalise("R/AskReddit") == "AskReddit"


def test_surrounding_whitespace_is_ignored():
    assert normalise("  r/news  ") == "news"


def test_something_that_is_not_a_subreddit_is_rejected():
    with pytest.raises(ValueError, match="not a subreddit"):
        normalise("https://example.com/news")


def test_an_empty_value_is_rejected():
    with pytest.raises(ValueError):
        normalise("   ")


def test_a_list_is_normalised_in_order_without_duplicates():
    given = ["r/news", "https://www.reddit.com/r/soccer/", "news"]
    assert normalise_all(given) == ["news", "soccer"]
