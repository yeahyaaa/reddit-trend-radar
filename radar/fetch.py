"""Read-only access to Reddit's listings.

Anonymously these are the same endpoints the website calls, with no API key and no
account. Reddit serves them to some networks and answers 403 to others, so the
first refusal in a run switches the whole run to the Atom feed rather than
re-asking once per subreddit and earning a rate limit.

With credentials configured (see radar/auth.py) requests go to oauth.reddit.com
instead, which has a far higher rate limit and, with a user login, can read
private subreddits the account belongs to.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import requests

from radar import auth, net
from radar.models import Post, SubredditResult
from radar.rss import fetch_rss

PAUSE_BETWEEN_CALLS = 3.0

PUBLIC_HOSTS = ("https://old.reddit.com", "https://www.reddit.com")
OAUTH_HOST = "https://oauth.reddit.com"

_json_blocked = False


class FetchError(RuntimeError):
    """Raised when a subreddit cannot be read."""


def reset_transport() -> None:
    """Forget what we learned about JSON availability. Used between runs and in tests."""
    global _json_blocked
    _json_blocked = False


def hosts() -> tuple[str, ...]:
    """The OAuth host when authenticated, the public ones otherwise."""
    return (OAUTH_HOST,) if auth.bearer_token() else PUBLIC_HOSTS


def fetch_subreddit(subreddit: str, period: str = "day", limit: int = 25) -> list[Post]:
    """Return the top posts of one subreddit, over whichever transport works."""
    global _json_blocked
    if not _json_blocked:
        try:
            return _fetch_json(subreddit, period, limit)
        except (FetchError, requests.RequestException, ValueError):
            _json_blocked = True
    return fetch_rss(subreddit, period, limit)


def fetch_each(
    subreddits: list[str], period: str = "day", limit: int = 25, pause: float | None = None
) -> Iterator[SubredditResult]:
    """Fetch subreddits one at a time, yielding each outcome as it lands.

    A generator rather than a list so a caller can report progress during a run
    that takes a minute, instead of going silent and then printing everything.
    """
    for name in subreddits:
        try:
            posts = fetch_subreddit(name, period, limit)
            yield SubredditResult(name, posts, source=_source_of(posts))
        except (FetchError, requests.RequestException) as exc:
            yield SubredditResult(name, error=str(exc))
        time.sleep(PAUSE_BETWEEN_CALLS if pause is None else pause)


def fetch_many(
    subreddits: list[str], period: str = "day", limit: int = 25
) -> tuple[list[Post], list[str]]:
    """The whole run at once, for callers that do not care about progress."""
    posts: list[Post] = []
    failures: list[str] = []
    for result in fetch_each(subreddits, period, limit):
        if result.ok:
            posts.extend(result.posts)
        else:
            failures.append(f"r/{result.subreddit}: {result.error}")
    return posts, failures


def _source_of(posts: list[Post]) -> str:
    return posts[0].source if posts else "json"


def _fetch_json(subreddit: str, period: str, limit: int) -> list[Post]:
    """Read the JSON listing, which carries score and comment counts."""
    params = {"t": period, "limit": limit}
    payload = _get_json_any_host(f"/r/{subreddit}/top.json", params)
    children = payload.get("data", {}).get("children", [])
    if not children:
        raise FetchError("empty JSON listing")
    return [_to_post(child.get("data", {})) for child in children]


def _get_json_any_host(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Try each host until one answers, then give up with the last error."""
    last_error = "no host configured"
    for host in hosts():
        try:
            return _get_json(host + path, params)
        except FetchError as exc:
            last_error = str(exc)
    raise FetchError(last_error)


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Perform the request and hand back parsed JSON, or raise FetchError."""
    response = net.get(url, params)
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code}")
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        # Reddit sometimes answers 200 with an HTML interstitial instead of JSON.
        raise FetchError("non-JSON response") from None
    return payload


def _iso(created_utc: Any) -> str:
    """Reddit gives epoch seconds; the rest of the pipeline speaks ISO."""
    if not isinstance(created_utc, int | float):
        return ""
    return datetime.fromtimestamp(created_utc, tz=UTC).isoformat()


def _one_line(selftext: Any) -> str:
    """Collapse the body to one line, keeping all of it. See radar/selftext.py."""
    if not isinstance(selftext, str):
        return ""
    return " ".join(selftext.split())


def _article(raw: dict[str, Any]) -> str:
    """The URL a link post points at, empty when the post is its own content."""
    url = raw.get("url") or ""
    return "" if not isinstance(url, str) or "reddit.com/" in url else url


def _to_post(raw: dict[str, Any]) -> Post:
    """Map one listing entry, keeping only the fields the pipeline uses."""
    return Post(
        title=raw.get("title") or "",
        subreddit=raw.get("subreddit") or "",
        permalink=raw.get("permalink") or "",
        url=raw.get("url") or "",
        score=raw.get("score"),
        num_comments=raw.get("num_comments"),
        upvote_ratio=raw.get("upvote_ratio"),
        author=raw.get("author") or "",
        published=_iso(raw.get("created_utc")),
        summary=_one_line(raw.get("selftext")),
        source_url=_article(raw),
        source="json",
    )
