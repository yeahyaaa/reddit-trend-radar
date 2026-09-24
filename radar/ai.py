"""Optional: asking a language model which posts are the same story.

Counting words tells you "hurricane" appeared eleven times. It cannot tell you that
four of your communities are covering the same storm and one is covering a different
one. That is a reading problem, not a counting problem, so it is the one part of this
tool worth handing to a model.

The architecture matters more than the prompt. The model is shown numbered posts with
their subreddit, title, source domain and a slice of the body — and **no URLs at all**.
It answers with post numbers. The links in the report are then attached from our own
data. A hallucinated link is therefore not unlikely, it is impossible: the model was
never in a position to write one.

Off unless a key is present. See radar/providers.py for which keys are recognised.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from radar.models import Post
from radar.providers import FreeModel, Provider, ProviderError, detect, free_models, request

BODY_CHARS = 280
MAX_POSTS = 120
MAX_STORIES = 12

# A group of one is not a grouping. The post is already listed under its own
# community with its links and body, so repeating it here says nothing twice.
MIN_POSTS_PER_STORY = 2

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

INSTRUCTIONS = """You are helping someone plan content by reading what a set of Reddit
communities discussed this period.

Below are numbered posts. Group together the ones covering the SAME underlying story or
question, including when they are worded differently or come from different communities.

Every group must contain at least two posts. A post that nothing else covers is not a
group, so leave it out entirely rather than listing it on its own. If nothing in the list
is covered twice, reply with an empty list.

Reply with JSON only, in exactly this shape:

{"stories": [{"headline": "...", "summary": "...", "posts": [1, 4, 9]}]}

- headline: one short line naming the story, in plain language
- summary: one or two sentences on what is actually being said, and where the
  communities differ if they do
- posts: the numbers of the posts in this group, from the list below

Order the groups with the most widely covered first. Do not invent posts, links or
details that are not in the list. Do not write anything outside the JSON."""


@dataclass(slots=True)
class Story:
    """A group of posts the model judged to be the same story."""

    headline: str
    summary: str
    posts: list[Post]

    @property
    def subreddits(self) -> list[str]:
        """Which communities carried it, in the order they appear, without repeats."""
        seen: dict[str, None] = {}
        for post in self.posts:
            seen.setdefault(post.subreddit, None)
        return list(seen)

    @property
    def community_count(self) -> int:
        return len(self.subreddits)


def analyse(
    posts: list[Post],
    provider_name: str | None,
    model: str | None,
    use_free: bool = False,
) -> tuple[list[Story], str]:
    """Group the posts into stories, and say which model did it.

    Returns an empty list when no key is configured, which is the normal state and
    not an error.
    """
    provider = detect(provider_name)
    if provider is None or not posts:
        return [], ""
    considered = posts[:MAX_POSTS]
    prompt = build_prompt(considered)
    if use_free:
        return _first_useful(provider, prompt, considered, free_models())
    used = model or provider.default_model
    return parse_stories(request(provider, prompt, model), considered) or [], used


def _first_useful(
    provider: Provider, prompt: str, posts: list[Post], models: list[FreeModel]
) -> tuple[list[Story], str]:
    """Try each free model until one returns something we can actually read.

    Judging a model on whether the HTTP call succeeded is not enough. A free model
    can answer with truncated JSON, or spend its whole budget reasoning and return
    nothing, and both read as success at the transport layer. What counts is whether
    stories came out the other end, so the loop lives here rather than in providers.
    """
    if not models:
        raise ProviderError("no free models available from OpenRouter right now")
    last = "none tried"
    for candidate in models:
        try:
            reply = request(provider, prompt, candidate.model_id, candidate.supports_json)
        except (ProviderError, requests.RequestException) as exc:
            # A timeout is a network error rather than a ProviderError, and a free
            # model that hangs should cost one wait, not the whole section.
            last = str(exc)
            continue
        stories = parse_stories(reply, posts)
        if stories is not None:
            return stories, candidate.model_id
        last = f"{candidate.model_id} answered but nothing readable came out of it"
    raise ProviderError(f"all {len(models)} free models failed; last said: {last}")


def build_prompt(posts: list[Post]) -> str:
    """Number the posts for the model, deliberately without their links."""
    lines = [INSTRUCTIONS, "", "Posts:"]
    for index, post in enumerate(posts, start=1):
        lines.append(f"[{index}] r/{post.subreddit} | {post.title}{_source(post)}")
        if post.summary:
            lines.append(f"    {post.summary[:BODY_CHARS]}")
    return "\n".join(lines)


def parse_stories(reply: str, posts: list[Post]) -> list[Story] | None:
    """Read the model's answer, or None when there was nothing readable in it.

    An empty list and None mean different things: the first is a model saying
    nothing was covered twice, which is a real answer, and the second is a reply we
    could not use, which is worth trying another model for.
    """
    payload = _json_from(reply)
    if payload is None or not isinstance(payload.get("stories"), list):
        return None
    stories = [_story(raw, posts) for raw in payload["stories"][:MAX_STORIES]]
    kept = [s for s in stories if s is not None and len(s.posts) >= MIN_POSTS_PER_STORY]
    kept.sort(key=lambda s: (s.community_count, len(s.posts)), reverse=True)
    return kept


def _source(post: Post) -> str:
    """The domain a post points at, which is a useful hint and not a link."""
    if not post.source_url:
        return ""
    return f" | source: {urlparse(post.source_url).netloc.removeprefix('www.')}"


def _json_from(reply: str) -> dict[str, Any] | None:
    """The first JSON object in the reply, ignoring fences and any surrounding prose."""
    match = _JSON_BLOCK.search(reply or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _story(raw: Any, posts: list[Post]) -> Story | None:
    """One group, or None when it names nothing real.

    Indices outside the list are dropped rather than trusted. A model that invents a
    post number should cost us that number, not the whole report.
    """
    if not isinstance(raw, dict):
        return None
    headline = str(raw.get("headline") or "").strip()
    chosen = [posts[i - 1] for i in _indices(raw.get("posts"), len(posts))]
    if not headline or not chosen:
        return None
    return Story(headline, str(raw.get("summary") or "").strip(), chosen)


def _indices(given: Any, count: int) -> list[int]:
    """The one-based post numbers that are actually in range, in order, once each."""
    if not isinstance(given, list):
        return []
    seen: dict[int, None] = {}
    for value in given:
        if isinstance(value, int) and 1 <= value <= count:
            seen.setdefault(value, None)
    return list(seen)
