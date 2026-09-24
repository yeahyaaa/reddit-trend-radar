"""Pulling the body of a text post out of the Atom feed's content field.

Reddit wraps a self-post's body in <div class="md"> and then appends its own
"submitted by ... [link] [comments]" furniture. A link or image post has no such
div at all, only the furniture. So the div is the whole test: what is inside it is
the author writing, and everything else is Reddit talking.
"""

from __future__ import annotations

from html.parser import HTMLParser

BLOCK_TAGS = frozenset({"p", "div", "br", "li", "blockquote", "h1", "h2", "h3", "pre"})


class _BodyExtractor(HTMLParser):
    """Collects text inside the first div.md, ignoring everything around it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._depth:
            self._depth += 1 if tag == "div" else 0
            if tag in BLOCK_TAGS:
                self.parts.append(" ")
        elif tag == "div" and dict(attrs).get("class") == "md":
            self._depth = 1

    def handle_endtag(self, tag: str) -> None:
        if self._depth and tag == "div":
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._depth:
            self.parts.append(data)


class _LinkFinder(HTMLParser):
    """Reads the href behind Reddit's own [link] anchor, which is the article."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found = ""
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        if data.strip() == "[link]" and self._href:
            self.found = self._href


def outbound_link(content_html: str | None) -> str:
    """The article a link post points at, or empty for a self post.

    Reddit renders the destination as a [link] anchor next to [comments]. On a text
    post both point back at the thread, so anything on reddit.com is discarded: a
    link to the post we are already showing is not a second source.
    """
    if not content_html:
        return ""
    finder = _LinkFinder()
    finder.feed(content_html)
    if "reddit.com/" in finder.found:
        return ""
    return finder.found


def body_text(content_html: str | None) -> str:
    """The post's own words, collapsed to a single line, in full.

    Nothing is cut here. Shortening is a presentation decision and belongs to
    whichever format is being rendered: a CSV or a spreadsheet should carry the
    whole thing, and only the printable report has a page to fit.
    """
    if not content_html:
        return ""
    extractor = _BodyExtractor()
    extractor.feed(content_html)
    return " ".join("".join(extractor.parts).split())
