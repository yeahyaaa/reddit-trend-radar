from radar import net
from radar.net import get, retry_delay


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


def queue_responses(monkeypatch, responses):
    """Serve the given responses in order, and record how long we slept."""
    slept = []
    pending = list(responses)
    monkeypatch.setattr(net, "_once", lambda url, params: pending.pop(0))
    monkeypatch.setattr(net.time, "sleep", lambda seconds: slept.append(seconds))
    return slept


def test_returns_immediately_on_success(monkeypatch):
    slept = queue_responses(monkeypatch, [FakeResponse(200)])
    assert get("https://example.test").status_code == 200
    assert slept == []


def test_retries_after_rate_limit_then_succeeds(monkeypatch):
    slept = queue_responses(monkeypatch, [FakeResponse(429), FakeResponse(200)])
    assert get("https://example.test").status_code == 200
    assert len(slept) == 1


def test_gives_up_and_returns_the_rate_limit(monkeypatch):
    responses = [FakeResponse(429) for _ in range(net.MAX_ATTEMPTS)]
    queue_responses(monkeypatch, responses)
    assert get("https://example.test").status_code == 429


def test_does_not_retry_other_error_codes(monkeypatch):
    slept = queue_responses(monkeypatch, [FakeResponse(403)])
    assert get("https://example.test").status_code == 403
    assert slept == []


def test_delay_honours_retry_after_header():
    assert retry_delay(FakeResponse(429, {"Retry-After": "7"}), 1) == 7.0


def test_delay_caps_an_absurd_retry_after():
    assert retry_delay(FakeResponse(429, {"Retry-After": "9000"}), 1) == 60.0


def test_delay_ignores_an_unparsable_retry_after():
    assert retry_delay(FakeResponse(429, {"Retry-After": "soon"}), 1) == net.BACKOFF_BASE


def test_delay_grows_with_each_attempt():
    first = retry_delay(FakeResponse(429), 1)
    second = retry_delay(FakeResponse(429), 2)
    assert second > first


def test_anonymous_requests_carry_no_authorization(monkeypatch):
    monkeypatch.setattr(net.auth, "bearer_token", lambda: None)
    assert "Authorization" not in net.headers()


def test_authenticated_requests_carry_a_bearer_token(monkeypatch):
    monkeypatch.setattr(net.auth, "bearer_token", lambda: "tok123")
    assert net.headers()["Authorization"] == "bearer tok123"


def test_every_request_identifies_itself(monkeypatch):
    monkeypatch.setattr(net.auth, "bearer_token", lambda: None)
    assert net.headers()["User-Agent"] == net.USER_AGENT
