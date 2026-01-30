"""Forbidden-language scanner used across unit and UI tests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

DEFAULT_FORBIDDEN_TERMS: tuple[str, ...] = (
    "compliance",
    "compliant",
    "breach",
    "breached",
    "violates",
    "violation",
    "satisfies",
    "satisfaction",
    "prevails",
    "stronger",
    "weaker",
    "valid",
    "invalid",
    "illegal",
    "lawful",
    "binding",
    "override",
)

_WORD_RE = re.compile(r"[a-zA-Z]+")


@dataclass(frozen=True)
class ForbiddenHit:
    term: str
    context: str


def scan_forbidden_language(
    text: str, forbidden_terms: Sequence[str] = DEFAULT_FORBIDDEN_TERMS
) -> list[ForbiddenHit]:
    """Return all occurrences of forbidden terms with a small context window.

    Conservative substring scan; fast and deterministic for tests.
    """

    lowered = (text or "").lower()
    hits: list[ForbiddenHit] = []
    for term in forbidden_terms:
        t = term.lower()
        start = 0
        while True:
            idx = lowered.find(t, start)
            if idx == -1:
                break
            lo = max(0, idx - 40)
            hi = min(len(lowered), idx + len(t) + 40)
            hits.append(ForbiddenHit(term=term, context=text[lo:hi]))
            start = idx + len(t)
    return hits


def assert_no_forbidden_language(
    text: str, forbidden_terms: Sequence[str] = DEFAULT_FORBIDDEN_TERMS
) -> None:
    hits = scan_forbidden_language(text, forbidden_terms)
    if hits:
        samples = "\n".join(f"- {hit.term}: ...{hit.context}..." for hit in hits[:10])
        raise AssertionError(f"Forbidden language detected ({len(hits)} hits):\n{samples}")
