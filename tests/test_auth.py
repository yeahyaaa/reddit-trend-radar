import pytest

from radar import auth
from radar.auth import AuthError, _grant, bearer_token


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test with no credentials and no cached token."""
    for name in ("CLIENT_ID", "CLIENT_SECRET", "USERNAME", "PASSWORD"):
        monkeypatch.delenv(f"REDDIT_{name}", raising=False)
    monkeypatch.setattr(auth, "_ensure_env_loaded", lambda: None)
    auth.reset()
    yield
    auth.reset()


def record_post(monkeypatch, response):
    """Capture the arguments of the token request instead of sending it."""
    calls = []

    def fake_post(url, data, auth, headers, timeout):
        calls.append({"url": url, "data": data, "auth": auth})
        return response

    monkeypatch.setattr(auth.requests, "post", fake_post)
    return calls


def test_no_credentials_means_anonymous(monkeypatch):
    record_post(monkeypatch, FakeResponse(200, {"access_token": "should not be used"}))
    assert bearer_token() is None


def test_client_id_without_secret_is_ignored(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "abc")
    record_post(monkeypatch, FakeResponse(200, {"access_token": "t"}))
    assert bearer_token() is None


def test_app_only_grant_when_no_login_is_given(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "abc")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "shh")
    calls = record_post(monkeypatch, FakeResponse(200, {"access_token": "app-token"}))
    assert bearer_token() == "app-token"
    assert calls[0]["data"]["grant_type"] == "client_credentials"
    assert calls[0]["auth"] == ("abc", "shh")


def test_password_grant_when_a_login_is_given(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "abc")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "shh")
    monkeypatch.setenv("REDDIT_USERNAME", "yahya")
    monkeypatch.setenv("REDDIT_PASSWORD", "hunter2")
    calls = record_post(monkeypatch, FakeResponse(200, {"access_token": "user-token"}))
    assert bearer_token() == "user-token"
    assert calls[0]["data"]["grant_type"] == "password"
    assert calls[0]["data"]["username"] == "yahya"


def test_a_username_without_a_password_falls_back_to_app_only():
    creds = {"client_id": "a", "client_secret": "b", "username": "yahya", "password": ""}
    assert _grant(creds)["grant_type"] == "client_credentials"


def test_rejected_credentials_raise_a_clear_error(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "abc")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "wrong")
    record_post(monkeypatch, FakeResponse(401))
    with pytest.raises(AuthError, match="401"):
        bearer_token()


def test_token_is_fetched_once_and_reused(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "abc")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "shh")
    calls = record_post(monkeypatch, FakeResponse(200, {"access_token": "t"}))
    bearer_token()
    bearer_token()
    assert len(calls) == 1


def test_anonymous_result_is_also_cached(monkeypatch):
    calls = record_post(monkeypatch, FakeResponse(200, {"access_token": "t"}))
    bearer_token()
    bearer_token()
    assert calls == []
