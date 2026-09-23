"""Optional Reddit OAuth.

Everything works without this. Supplying credentials buys two things: Reddit's
authenticated rate limit instead of the anonymous one, and, if you also give a
login, access to subreddits you are a member of but the public cannot read.

Two grants, picked automatically:

  client_id + client_secret            -> app-only token. Higher rate limit,
                                          public subreddits only. No password
                                          goes anywhere.
  client_id + client_secret + login    -> user token. Everything above, plus the
                                          private subreddits your account can see.

Credentials are read from the environment or a .env file, never from the code.
"""

import os

import requests

from radar import USER_AGENT

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REQUEST_TIMEOUT = 15

_UNSET = object()
_cached_token: str | None | object = _UNSET


class AuthError(RuntimeError):
    """Raised when Reddit rejects the credentials it was given."""


def bearer_token() -> str | None:
    """The OAuth token for this run, or None when running anonymously."""
    global _cached_token
    if _cached_token is _UNSET:
        _cached_token = _request_token(_credentials())
    return _cached_token if isinstance(_cached_token, str) else None


def reset() -> None:
    """Forget the cached token, so the next call re-reads the environment."""
    global _cached_token
    _cached_token = _UNSET


def _credentials() -> dict[str, str]:
    _ensure_env_loaded()
    names = ("client_id", "client_secret", "username", "password")
    return {name: os.environ.get(f"REDDIT_{name.upper()}", "").strip() for name in names}


def _grant(credentials: dict[str, str]) -> dict[str, str]:
    """Password grant when a full login is given, app-only otherwise."""
    if credentials["username"] and credentials["password"]:
        return {
            "grant_type": "password",
            "username": credentials["username"],
            "password": credentials["password"],
        }
    return {"grant_type": "client_credentials"}


def _request_token(credentials: dict[str, str]) -> str | None:
    """Exchange the credentials for a token, or return None if there are none."""
    if not credentials["client_id"] or not credentials["client_secret"]:
        return None
    response = requests.post(
        TOKEN_URL,
        data=_grant(credentials),
        auth=(credentials["client_id"], credentials["client_secret"]),
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise AuthError(f"Reddit rejected the credentials (HTTP {response.status_code})")
    token = response.json().get("access_token")
    return str(token) if token else None


def _ensure_env_loaded() -> None:
    # python-dotenv is optional: without it, real environment variables still work.
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()
