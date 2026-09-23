from radar.keywords import extract_keywords, tokenize
from radar.models import Post


def titled(title):
    return Post(title=title, subreddit="ubuntu")


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Ubuntu 26.04 LTS, released!") == ["ubuntu", "26", "04", "lts", "released"]


def test_tokenize_drops_stopwords_and_short_tokens():
    assert tokenize("this is a the of Kubernetes") == ["kubernetes"]


def test_tokenize_handles_a_missing_title():
    assert tokenize(None) == []


def test_extract_counts_across_posts():
    posts = [
        titled("Kubernetes on Ubuntu"),
        titled("Kubernetes networking"),
        titled("Snap packages"),
    ]
    assert extract_keywords(posts, 1) == [("kubernetes", 2)]


def test_extract_respects_top_n():
    assert len(extract_keywords([titled("alpha beta gamma delta")], 2)) == 2


def test_extract_handles_empty_titles():
    assert extract_keywords([titled(""), titled("")], 3) == []
