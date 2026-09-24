"""Accepting a subreddit however someone happens to have it to hand.

People copy a URL out of the address bar far more often than they type a name, so
taking only bare names would mean asking them to edit every one by hand.
"""

from __future__ import annotations

import re

_FROM_URL = re.compile(r"(?:^|/)r/([A-Za-z0-9_]{2,21})(?:/|$)", re.IGNORECASE)
_BARE_NAME = re.compile(r"^[A-Za-z0-9_]{2,21}$")


def normalise(given: str) -> str:
    """Turn a name, an r/ prefix or a full Reddit URL into the bare name."""
    text = given.strip().strip("/")
    if not text:
        raise ValueError("not a subreddit: empty value")
    match = _FROM_URL.search(text)
    if match:
        return match.group(1)
    if _BARE_NAME.match(text):
        return text
    raise ValueError(f"not a subreddit: {given!r}")


def normalise_all(given: list[str]) -> list[str]:
    """Normalise a list, keeping the order asked for and dropping repeats."""
    seen: dict[str, None] = {}
    for item in given:
        seen.setdefault(normalise(item), None)
    return list(seen)
