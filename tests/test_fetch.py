import pytest

from radar import fetch
from radar.fetch import FetchError, _get_json_any_host, _to_post, fetch_many


@pytest.fixture(autouse=True)
def anonymous(monkeypatch):
    """Default to the anonymous transport and a clean slate for every test."""
    monkeypatch.setattr(fetch.auth, "bearer_token", lambda: None)
    fetch.reset_transport()
    yield
    fetch.reset_transport()


def test_to_post_keeps_only_the_fields_we_use():
    post = _to_post({"title": "t", "score": 3, "subreddit": "ubuntu", "selftext": "ignore me"})
    assert post.title == "t"
    assert post.score == 3
    assert post.upvote_ratio is None
    assert post.source == "json"


def test_to_post_survives_a_listing_entry_with_nothing_in_it():
    post = _to_post({})
    assert post.title == ""
    assert post.has_metrics is False


def test_anonymous_runs_use_the_public_hosts():
    assert fetch.hosts() == fetch.PUBLIC_HOSTS


def test_authenticated_runs_use_the_oauth_host(monkeypatch):
    monkeypatch.setattr(fetch.auth, "bearer_token", lambda: "tok123")
    assert fetch.hosts() == (fetch.OAUTH_HOST,)


def test_host_fallback_uses_the_second_host_when_the_first_fails(monkeypatch):
    tried = []

    def fake_get_json(url, params):
        tried.append(url)
        if "old.reddit" in url:
            raise FetchError("HTTP 403")
        return {"ok": True}

    monkeypatch.setattr(fetch, "_get_json", fake_get_json)
    assert _get_json_any_host("/r/x/top.json", {}) == {"ok": True}
    assert len(tried) == 2


def test_host_fallback_raises_when_every_host_fails(monkeypatch):
    def always_fails(url, params):
        raise FetchError("HTTP 500")

    monkeypatch.setattr(fetch, "_get_json", always_fails)
    with pytest.raises(FetchError, match="HTTP 500"):
        _get_json_any_host("/r/x/top.json", {})


def test_json_is_not_retried_once_it_has_been_refused(monkeypatch):
    """The first refusal should teach the run to stop asking, not repeat six times."""
    json_attempts = []

    def failing_json(subreddit, period, limit):
        json_attempts.append(subreddit)
        raise FetchError("HTTP 403")

    monkeypatch.setattr(fetch, "_fetch_json", failing_json)
    monkeypatch.setattr(fetch, "fetch_rss", lambda s, p, limit: [_to_post({"title": s})])
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)

    posts, failures = fetch_many(["ubuntu", "linux", "devops"], "day", 5)
    assert json_attempts == ["ubuntu"]
    assert len(posts) == 3
    assert failures == []


def test_transport_reset_allows_json_again(monkeypatch):
    monkeypatch.setattr(fetch, "_fetch_json", lambda s, p, limit: [_to_post({"title": s})])
    assert fetch.fetch_subreddit("ubuntu", "day", 5)[0].title == "ubuntu"


def test_fetch_many_skips_failing_subreddits(monkeypatch):
    def fake_fetch(subreddit, period, limit):
        if subreddit == "broken":
            raise FetchError("HTTP 404")
        return [_to_post({"title": subreddit})]

    monkeypatch.setattr(fetch, "fetch_subreddit", fake_fetch)
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)
    posts, failures = fetch_many(["ubuntu", "broken"], "day", 5)
    assert [p.title for p in posts] == ["ubuntu"]
    assert failures == ["r/broken: HTTP 404"]


def test_the_pause_between_subreddits_can_be_raised(monkeypatch):
    """Data-centre addresses get throttled harder and need a longer gap."""
    slept = []
    monkeypatch.setattr(fetch, "fetch_subreddit", lambda s, p, limit: [])
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: slept.append(seconds))
    list(fetch.fetch_each(["ubuntu", "linux"], "day", 5, pause=12.0))
    assert slept == [12.0, 12.0]


def test_the_default_pause_is_used_when_none_is_given(monkeypatch):
    slept = []
    monkeypatch.setattr(fetch, "fetch_subreddit", lambda s, p, limit: [])
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: slept.append(seconds))
    list(fetch.fetch_each(["ubuntu"], "day", 5))
    assert slept == [fetch.PAUSE_BETWEEN_CALLS]
