import pytest

from radar import providers
from radar.providers import PROVIDERS, ProviderError, detect, request


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for provider in PROVIDERS.values():
        monkeypatch.delenv(provider.env_var, raising=False)


class TestDetection:
    def test_no_key_anywhere_means_no_provider(self):
        assert detect(None) is None

    def test_a_single_key_is_found_without_being_named(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert detect(None).name == "openai"

    def test_an_explicit_choice_wins_over_what_else_is_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert detect("anthropic").name == "anthropic"

    def test_asking_for_a_provider_with_no_key_is_an_error(self):
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            detect("anthropic")

    def test_asking_for_a_provider_that_does_not_exist_is_an_error(self):
        with pytest.raises(ProviderError, match="unknown provider"):
            detect("hal9000")

    def test_every_provider_declares_a_key_a_model_and_a_url(self):
        for provider in PROVIDERS.values():
            assert provider.env_var.endswith("_API_KEY")
            assert provider.default_model
            assert provider.url.startswith("https://")


class TestRequestShapes:
    """Each provider wants a different body and hides the answer somewhere else."""

    def capture(self, monkeypatch, payload):
        seen = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return payload

            @property
            def text(self):
                return str(payload)

        def fake_post(url, headers=None, json=None, timeout=None):
            seen.update(url=url, headers=headers, body=json)
            return FakeResponse()

        monkeypatch.setattr(providers.requests, "post", fake_post)
        return seen

    def test_anthropic_sends_its_key_header_and_reads_the_content_block(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        seen = self.capture(monkeypatch, {"content": [{"type": "text", "text": "hello"}]})
        assert request(detect("anthropic"), "prompt", None) == "hello"
        assert seen["headers"]["x-api-key"] == "sk-ant-test"
        assert "anthropic-version" in seen["headers"]

    def test_openai_sends_a_bearer_token_and_reads_the_first_choice(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        payload = {"choices": [{"message": {"content": "hello"}}]}
        seen = self.capture(monkeypatch, payload)
        assert request(detect("openai"), "prompt", None) == "hello"
        assert seen["headers"]["Authorization"] == "Bearer sk-test"

    def test_openrouter_uses_the_same_shape_as_openai(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        payload = {"choices": [{"message": {"content": "hello"}}]}
        seen = self.capture(monkeypatch, payload)
        assert request(detect("openrouter"), "prompt", None) == "hello"
        assert "openrouter.ai" in seen["url"]

    def test_gemini_puts_the_key_in_the_url_and_reads_a_candidate(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AI-test")
        payload = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
        seen = self.capture(monkeypatch, payload)
        assert request(detect("gemini"), "prompt", None) == "hello"
        assert "key=AI-test" in seen["url"]

    def test_an_explicit_model_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        seen = self.capture(monkeypatch, {"choices": [{"message": {"content": "x"}}]})
        request(detect("openai"), "prompt", "gpt-4.1-mini")
        assert seen["body"]["model"] == "gpt-4.1-mini"

    def test_the_default_model_is_used_when_none_is_given(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        seen = self.capture(monkeypatch, {"choices": [{"message": {"content": "x"}}]})
        request(detect("openai"), "prompt", None)
        assert seen["body"]["model"] == PROVIDERS["openai"].default_model


class TestFailures:
    def test_a_rejected_request_says_which_provider_and_what_status(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        class Rejected:
            status_code = 401
            text = "invalid key"

            def json(self):
                return {}

        monkeypatch.setattr(providers.requests, "post", lambda *a, **k: Rejected())
        with pytest.raises(ProviderError, match="openai.*401"):
            request(detect("openai"), "prompt", None)

    def test_an_answer_in_an_unexpected_shape_is_an_error_not_a_crash(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        class Odd:
            status_code = 200
            text = "{}"

            def json(self):
                return {"unexpected": True}

        monkeypatch.setattr(providers.requests, "post", lambda *a, **k: Odd())
        with pytest.raises(ProviderError, match="could not read"):
            request(detect("openai"), "prompt", None)


class TestEmptyReplies:
    """A reasoning model can spend the whole budget thinking and return nothing."""

    def respond(self, monkeypatch, payload):
        class FakeResponse:
            status_code = 200
            text = str(payload)

            def json(self):
                return payload

        monkeypatch.setattr(providers.requests, "post", lambda *a, **k: FakeResponse())

    def test_a_null_content_is_a_failure_not_an_empty_answer(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        self.respond(monkeypatch, {"choices": [{"message": {"content": None}}]})
        with pytest.raises(ProviderError, match="empty"):
            request(detect("openai"), "prompt", None)

    def test_an_empty_string_is_also_a_failure(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        self.respond(monkeypatch, {"choices": [{"message": {"content": "   "}}]})
        with pytest.raises(ProviderError, match="empty"):
            request(detect("openai"), "prompt", None)

    def test_running_out_of_room_is_named_so_the_cause_is_obvious(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        payload = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
        self.respond(monkeypatch, payload)
        with pytest.raises(ProviderError, match="ran out of room"):
            request(detect("openai"), "prompt", None)

    def test_an_empty_anthropic_content_block_is_a_failure(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        self.respond(monkeypatch, {"content": []})
        with pytest.raises(ProviderError, match="empty"):
            request(detect("anthropic"), "prompt", None)

    def test_the_budget_leaves_room_for_a_model_that_thinks_first(self):
        """4000 was not enough: one free model spent 4074 tokens reasoning."""
        assert providers.MAX_TOKENS >= 16000
