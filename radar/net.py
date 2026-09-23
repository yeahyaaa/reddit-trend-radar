"""Shared HTTP behaviour: one user agent, one timeout, one retry policy.

Reddit answers 429 when asked for too much too quickly. Rather than dropping a
subreddit on the first refusal, wait and ask again, preferring Reddit's own
Retry-After header over our guess.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from radar import USER_AGENT, auth

REQUEST_TIMEOUT = 15
MAX_ATTEMPTS = 4
BACKOFF_BASE = 4.0
MAX_BACKOFF = 60.0


def get(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    """GET a URL, waiting and retrying while Reddit rate-limits us."""
    response = _once(url, params)
    for attempt in range(1, MAX_ATTEMPTS):
        if response.status_code != 429:
            return response
        time.sleep(retry_delay(response, attempt))
        response = _once(url, params)
    return response


def retry_delay(response: requests.Response, attempt: int) -> float:
    """Seconds to wait before retrying: Reddit's own figure if it gave one."""
    stated = response.headers.get("Retry-After")
    if stated:
        try:
            return min(float(stated), MAX_BACKOFF)
        except ValueError:
            pass
    return min(BACKOFF_BASE * 2.0 ** (attempt - 1), MAX_BACKOFF)


def headers() -> dict[str, str]:
    """Identify the script, and authenticate when credentials are configured."""
    built = {"User-Agent": USER_AGENT}
    token = auth.bearer_token()
    if token:
        built["Authorization"] = f"bearer {token}"
    return built


def _once(url: str, params: dict[str, Any] | None) -> requests.Response:
    return requests.get(url, params=params, headers=headers(), timeout=REQUEST_TIMEOUT)
