"""Falling over between free models when one is spent or answers with rubbish."""

import json

import pytest

from radar import ai
from radar.ai import _first_useful
from radar.models import Post
from radar.providers import PROVIDERS, FreeModel, ProviderError

POSTS = [
    Post(title="Hurricane hits", subreddit="news", permalink="/r/news/1"),
    Post(title="Storm coverage", subreddit="worldnews", permalink="/r/worldnews/2"),
]

GOOD = json.dumps({"stories": [{"headline": "Storm", "summary": "s", "posts": [1, 2]}]})
MODELS = [
    FreeModel("first:free", True, 1000, True),
    FreeModel("second:free", True, 900, True),
]


def serve(monkeypatch, answers):
    """Answer each model with a string, or raise whatever is given instead."""
    tried = []

    def fake(provider, prompt, model, supports_json=True):
        tried.append(model)
        answer = answers[model]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(ai, "request", fake)
    return tried


def run():
    return _first_useful(PROVIDERS["openrouter"], "prompt", POSTS, MODELS)


def test_the_first_model_that_answers_usefully_is_used(monkeypatch):
    tried = serve(monkeypatch, {"first:free": GOOD})
    stories, used = run()
    assert used == "first:free"
    assert stories[0].headline == "Storm"
    assert tried == ["first:free"]


def test_a_model_out_of_quota_hands_over_to_the_next(monkeypatch):
    """Free tiers run dry constantly; one dry model should not end the run."""
    answers = {"first:free": ProviderError("429 rate limited"), "second:free": GOOD}
    tried = serve(monkeypatch, answers)
    _, used = run()
    assert used == "second:free"
    assert tried == ["first:free", "second:free"]


def test_truncated_json_also_hands_over(monkeypatch):
    """A cut-off reply is a 200 at the transport layer and still useless here."""
    answers = {"first:free": '{"stories": [{"headline": "Sto', "second:free": GOOD}
    tried = serve(monkeypatch, answers)
    _, used = run()
    assert used == "second:free"
    assert tried == ["first:free", "second:free"]


def test_an_honest_empty_answer_is_accepted_without_trying_more_models(monkeypatch):
    """Nothing covered twice is a finding. Rotating past it would burn nine more calls."""
    tried = serve(monkeypatch, {"first:free": json.dumps({"stories": []})})
    stories, used = run()
    assert stories == []
    assert used == "first:free"
    assert tried == ["first:free"]


def test_a_reply_in_the_wrong_shape_hands_over(monkeypatch):
    answers = {"first:free": '{"result": "done"}', "second:free": GOOD}
    serve(monkeypatch, answers)
    _, used = run()
    assert used == "second:free"


def test_when_every_model_fails_the_last_reason_is_reported(monkeypatch):
    serve(monkeypatch, {m.model_id: ProviderError(f"{m.model_id} is out") for m in MODELS})
    with pytest.raises(ProviderError, match="all 2 free models failed.*second:free is out"):
        run()


def test_a_model_that_answers_unreadably_is_named_as_such(monkeypatch):
    serve(monkeypatch, {m.model_id: "not json at all" for m in MODELS})
    with pytest.raises(ProviderError, match="nothing readable came out"):
        run()


def test_an_empty_model_list_is_an_error_worth_naming():
    with pytest.raises(ProviderError, match="no free models"):
        _first_useful(PROVIDERS["openrouter"], "prompt", POSTS, [])


def test_json_support_is_passed_through_per_model(monkeypatch):
    seen = {}

    def fake(provider, prompt, model, supports_json=True):
        seen[model] = supports_json
        return GOOD

    monkeypatch.setattr(ai, "request", fake)
    _first_useful(PROVIDERS["openrouter"], "prompt", POSTS, [FreeModel("plain:free", False, 100)])
    assert seen["plain:free"] is False


def test_a_model_that_times_out_hands_over(monkeypatch):
    """A read timeout is a network error, not a ProviderError, and must not end the run."""
    import requests

    answers = {"first:free": requests.Timeout("read timed out"), "second:free": GOOD}
    tried = serve(monkeypatch, answers)
    _, used = run()
    assert used == "second:free"
    assert tried == ["first:free", "second:free"]


def test_a_connection_failure_also_hands_over(monkeypatch):
    import requests

    answers = {"first:free": requests.ConnectionError("dropped"), "second:free": GOOD}
    serve(monkeypatch, answers)
    _, used = run()
    assert used == "second:free"
