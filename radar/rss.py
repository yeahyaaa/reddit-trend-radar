"""Atom feed fallback.

Reddit refuses the JSON listings from some networks but still serves the public
Atom feed to anyone. The feed carries titles and links but no score or comment
count, so posts sourced this way keep Reddit's own ordering instead of being
re-ranked, and the report says so.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from radar import net
from radar.models import Post

ATOM = "{http://www.w3.org/2005/Atom}"
REDDIT_ROOT = "https://www.reddit.com"


def fetch_rss(subreddit: str, period: str = "day", limit: int = 25) -> list[Post]:
    """Pull one subreddit's top entries from its Atom feed."""
    response = net.get(f"{REDDIT_ROOT}/r/{subreddit}/top.rss", {"t": period, "limit": limit})
    response.raise_for_status()
    return parse_atom(response.text, subreddit)


def parse_atom(xml_text: str, subreddit: str) -> list[Post]:
    """Turn an Atom feed into the same Post shape the JSON path produces."""
    root = ElementTree.fromstring(xml_text)
    posts = []
    for entry in root.findall(f"{ATOM}entry"):
        post = _entry_to_post(entry, subreddit)
        if post is not None:
            posts.append(post)
    return posts


def _entry_to_post(entry: ElementTree.Element, subreddit: str) -> Post | None:
    """Map one Atom entry, or None when it carries no usable title."""
    title = entry.findtext(f"{ATOM}title")
    if not title:
        return None
    href = _href(entry)
    return Post(
        title=title,
        subreddit=subreddit,
        permalink=href.replace(REDDIT_ROOT, "", 1),
        url=href,
        source="rss",
    )


def _href(entry: ElementTree.Element) -> str:
    link = entry.find(f"{ATOM}link")
    return "" if link is None else link.get("href", "")
