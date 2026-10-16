"""Decide whether a piece of extracted text is teachable prose.

A textbook contains many pages that hold real sentences and no teachable content:
tables of contents, chapter outlines, indexes, bibliographies and recommended-reading
lists. They survive a word-count filter because author names are words, so they are
detected by shape instead.

This module is the single definition used in two places:
  * ingest, to skip a page before it is ever chunked and embedded
  * the quiz agent, to avoid building a question from a passage that has no content

Filtering at ingest is the real fix. Filtering at query time, which is where this
started, only hides the pages after they have already taken up space in the index and
competed for retrieval slots.
"""

from __future__ import annotations

import re

# Slides are terser than textbook prose by design, so one threshold for both either
# lets contents pages through or throws away the best lecture material.
MIN_CHARS = {"page": 250, "slide": 100}
MIN_WORD_RATIO = {"page": 0.55, "slide": 0.45}
MAX_NUMERIC_RATIO = 0.12   # contents and index pages are mostly page numbers
MAX_REF_TAGS = 2           # [KOHL89]-style citation keys
MAX_INITIALS = 3           # "Kumar, M." author initials
MAX_YEARS = 3              # publication years

_PROSE_WORD = re.compile(r"^[A-Za-z][A-Za-z'-]{2,}$")
_REF_TAG = re.compile(r"\[[A-Z]{2,5}\d{2}[a-z]?\]")
_INITIALS = re.compile(r"\b[A-Z]\.\s")
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_LEADER = re.compile(r"(?:\.\s*){4,}")          # dotted leaders, a contents page
_SECTION_HEAD = re.compile(
    r"^\s*(references|bibliography|index|contents|glossary|preface|"
    r"acknowledge?ments|recommended reading|further reading|about the author)\b",
    re.IGNORECASE,
)
_FRONT_MATTER = re.compile(
    r"(table of contents|contents at a glance|list of (figures|tables)|"
    r"recommended reading and web sites|key terms, review questions|isbn)",
    re.IGNORECASE,
)

# Bullet glyphs survive extraction as their own tokens and would otherwise count
# against the prose ratio on every slide.
_STRIP_CHARS = ".,;:()[]•�∙-"


def is_prose(text: str, kind: str = "page") -> bool:
    """True when the text holds prose worth embedding or asking a question about."""
    text = text.strip()
    if len(text) < MIN_CHARS.get(kind, 250):
        return False

    tokens = text.split()
    if not tokens:
        return False

    stripped = [t.strip(_STRIP_CHARS) for t in tokens]
    prose = sum(1 for t in stripped if _PROSE_WORD.match(t))
    if prose / len(tokens) < MIN_WORD_RATIO.get(kind, 0.55):
        return False

    numeric = sum(1 for t in stripped if t.isdigit())
    if numeric / len(tokens) > MAX_NUMERIC_RATIO:
        return False

    if _LEADER.search(text):
        return False
    if _SECTION_HEAD.match(text) or _FRONT_MATTER.search(text[:600]):
        return False
    if len(_REF_TAG.findall(text)) > MAX_REF_TAGS:
        return False

    initials = len(_INITIALS.findall(text))
    if initials > MAX_INITIALS:
        return False
    if len(_YEAR.findall(text)) > MAX_YEARS and initials >= 2:
        return False

    return True
