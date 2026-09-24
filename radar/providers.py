"""One shape for four language model APIs.

Anthropic, OpenAI, Gemini and OpenRouter all take a prompt and return text, and all
four disagree about where the key goes, what the body looks like and where the
answer hides. This flattens that to `detect()` and `request()`.

No SDKs. Four HTTP calls do not justify four dependencies, and the shapes below are
each about six lines.

Which provider runs is decided by which key is in the environment. Set one and it
is used; set several and say which with --ai-provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

REQUEST_TIMEOUT = 120
# Reasoning models spend the budget thinking before they write a word. One free
# model burned 4074 tokens reasoning and returned nothing, so this is generous.
MAX_TOKENS = 16000

CATALOGUE_URL = "https://openrouter.ai/api/v1/models"
FREE_MODEL_LIMIT = 10


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured or answers with something unusable."""


@dataclass(frozen=True)
class FreeModel:
    """One of OpenRouter's free models, with what it can be relied on to do."""

    model_id: str
    supports_json: bool
    context_length: int
    # A model that guarantees a schema is steadier than one that merely accepts
    # response_format, so the two are kept apart for ranking.
    structured: bool = False


@dataclass(frozen=True)
class Provider:
    """Everything that differs between one model API and the next."""

    name: str
    env_var: str
    url: str
    default_model: str
    key: str = ""


# Defaults age. Every one of these can be replaced with --ai-model, and the README
# says so, because a hard-coded model name is the first thing to rot in a tool like this.
PROVIDERS: dict[str, Provider] = {
    "anthropic": Provider(
        name="anthropic",
        env_var="ANTHROPIC_API_KEY",
        url="https://api.anthropic.com/v1/messages",
        default_model="claude-sonnet-5",
    ),
    "openai": Provider(
        name="openai",
        env_var="OPENAI_API_KEY",
        url="https://api.openai.com/v1/chat/completions",
        default_model="gpt-5.2",
    ),
    "gemini": Provider(
        name="gemini",
        env_var="GEMINI_API_KEY",
        url="https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        default_model="gemini-2.5-pro",
    ),
    "openrouter": Provider(
        name="openrouter",
        env_var="OPENROUTER_API_KEY",
        url="https://openrouter.ai/api/v1/chat/completions",
        default_model="anthropic/claude-sonnet-5",
    ),
}


def detect(chosen: str | None) -> Provider | None:
    """The provider to use, or None when no key is configured at all.

    Naming one that has no key is an error rather than a silent fallback: being
    quietly downgraded to a different model than you asked for is worse than being
    told to set the variable.
    """
    if chosen:
        if chosen not in PROVIDERS:
            raise ProviderError(f"unknown provider {chosen!r}; try {', '.join(PROVIDERS)}")
        provider = PROVIDERS[chosen]
        key = os.environ.get(provider.env_var, "").strip()
        if not key:
            raise ProviderError(f"{chosen} needs {provider.env_var} in the environment")
        return Provider(**{**provider.__dict__, "key": key})
    for provider in PROVIDERS.values():
        key = os.environ.get(provider.env_var, "").strip()
        if key:
            return Provider(**{**provider.__dict__, "key": key})
    return None


def free_models(limit: int = FREE_MODEL_LIMIT) -> list[FreeModel]:
    """OpenRouter's free models right now, best first.

    Fetched rather than hard-coded: the free tier churns, and a list baked into the
    source would be wrong within a month.
    """
    response = requests.get(CATALOGUE_URL, timeout=30)
    if response.status_code != 200:
        raise ProviderError(f"could not read OpenRouter's model list: {response.status_code}")
    return rank_free(response.json(), limit)


def rank_free(catalogue: Any, limit: int = FREE_MODEL_LIMIT) -> list[FreeModel]:
    """Rank the free models on what the catalogue says they can do.

    Being able to return guaranteed JSON matters more here than a long context,
    because the whole step is a structured answer. Ranking on the API's own
    metadata avoids an opinion about which model is "best", which would rot.
    """
    entries = catalogue.get("data") if isinstance(catalogue, dict) else None
    if not isinstance(entries, list):
        return []
    found = [_free_model(entry) for entry in entries if _is_free(entry)]
    found.sort(key=lambda m: (m.structured, m.supports_json, m.context_length), reverse=True)
    return found[:limit]


def _is_free(entry: Any) -> bool:
    return isinstance(entry, dict) and str(entry.get("id", "")).endswith(":free")


def _free_model(entry: dict[str, Any]) -> FreeModel:
    """Read one catalogue entry, treating absent fields as absent capability."""
    params = set(entry.get("supported_parameters") or [])
    structured = "structured_outputs" in params
    return FreeModel(
        model_id=str(entry["id"]),
        supports_json=structured or "response_format" in params,
        context_length=int(entry.get("context_length") or 0),
        structured=structured,
    )


def request(
    provider: Provider, prompt: str, model: str | None, supports_json: bool = True
) -> str:
    """Send one prompt and return the text of the reply."""
    name = model or provider.default_model
    response = requests.post(
        _url(provider, name),
        headers=_headers(provider),
        json=_body(provider, prompt, name, supports_json),
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        detail = response.text[:200]
        raise ProviderError(f"{provider.name} returned {response.status_code}: {detail}")
    payload = response.json()
    try:
        text = _extract(provider, payload)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError(f"could not read {provider.name}'s reply: {exc}") from None
    if not text.strip():
        raise ProviderError(_empty_reason(provider, payload, name))
    return text


def _empty_reason(provider: Provider, payload: dict[str, Any], model: str) -> str:
    """Why nothing came back, so the fallover message is worth reading.

    An empty answer has to be an error rather than an empty result: read as "no
    stories found" it would quietly replace a real answer with silence.
    """
    finish = ""
    if isinstance(payload.get("choices"), list) and payload["choices"]:
        finish = str(payload["choices"][0].get("finish_reason") or "")
    if finish == "length":
        return f"{model} ran out of room before answering; its reply was empty"
    return f"{provider.name} returned an empty reply from {model}"


def _url(provider: Provider, model: str) -> str:
    """Gemini names the model in the path and carries the key in the query string."""
    if provider.name == "gemini":
        return provider.url.format(model=model) + f"?key={provider.key}"
    return provider.url


def _headers(provider: Provider) -> dict[str, str]:
    base = {"content-type": "application/json"}
    if provider.name == "anthropic":
        return {**base, "x-api-key": provider.key, "anthropic-version": "2023-06-01"}
    if provider.name == "gemini":
        return base
    return {**base, "Authorization": f"Bearer {provider.key}"}


def _body(
    provider: Provider, prompt: str, model: str, supports_json: bool = True
) -> dict[str, Any]:
    """The request body, asking for JSON wherever the provider can enforce it."""
    if provider.name == "anthropic":
        return {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
    if provider.name == "gemini":
        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": MAX_TOKENS,
                "response_mime_type": "application/json",
            },
        }
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Sending response_format to a model that does not advertise it can be rejected
    # outright, so it goes in only when the catalogue says the model takes it.
    if supports_json:
        body["response_format"] = {"type": "json_object"}
    return body


def _extract(provider: Provider, payload: dict[str, Any]) -> str:
    """Dig the text out of whichever shape came back."""
    if provider.name == "anthropic":
        blocks = payload["content"]
        return "".join(b["text"] for b in blocks if b.get("type") == "text")
    if provider.name == "gemini":
        return _text(payload["candidates"][0]["content"]["parts"][0]["text"])
    return _text(payload["choices"][0]["message"]["content"])


def _text(value: Any) -> str:
    """A null content field means no answer, not the four letters "None"."""
    return "" if value is None else str(value)
