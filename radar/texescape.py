"""Making arbitrary internet text safe to put in a pdflatex document.

Two separate hazards, both of which kill a build rather than just looking wrong:

  LaTeX syntax   Reddit titles are full of & % _ # $ { } ~ ^. One unescaped percent
                 sign comments out the rest of a line, so a paragraph goes missing
                 from the PDF with no error at all.

  Unicode        pdflatex has no glyph for an emoji and refuses the whole document
                 over one. Post bodies are full of them. Typographic characters are
                 folded to their ASCII equivalents and anything else outside Latin
                 is dropped, which costs a character and saves the build.

Switching to xelatex would handle Unicode natively, at the price of a heavier
toolchain for everyone compiling the output. Dropping the emoji is the cheaper trade.
"""

from __future__ import annotations

import unicodedata

ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# Typography the web uses and a keyboard does not have.
FOLDED = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "′": "'", "″": '"',
    "–": "--", "—": "---", "―": "---", "−": "-",
    "…": "...", " ": " ", "​": "", "﻿": "",
    "•": "-", "·": "-", "→": "->", "←": "<-",
}

# Latin-1 Supplement through Latin Extended-B: accented letters pdflatex can set.
LATIN_CEILING = 0x24F


def escape(text: str) -> str:
    """Make text safe to drop into a LaTeX document."""
    return "".join(ESCAPES.get(character, character) for character in _to_latin(text))


def _to_latin(text: str) -> str:
    """Fold web typography to ASCII and drop anything pdflatex cannot set."""
    return "".join(_fold(character) for character in text)


def _fold(character: str) -> str:
    """One character's replacement: itself, an ASCII stand-in, or nothing."""
    if character in FOLDED:
        return FOLDED[character]
    if ord(character) <= LATIN_CEILING:
        return character
    # Keep a letter or digit that decomposes to Latin, such as a fullwidth A.
    stripped = unicodedata.normalize("NFKD", character)
    kept = "".join(c for c in stripped if c.isascii() and (c.isalnum() or c.isspace()))
    return kept or " "
