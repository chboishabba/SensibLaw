"""Reusable cue extraction helpers for deterministic text matching."""
from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from .shared_text_normalization import tokenize_canonical_text

_WHITESPACE_RE = re.compile(r"\s+")
_REGEX_HINT_RE = re.compile(r"[.\\^$*+?{}\[\]|()]")


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "").casefold()).strip()


def _normalize_cue(cue: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(cue or "").casefold()).strip()


def _cue_matches(normalized_text: str, token_set: frozenset[str], cue: str) -> bool:
    if _REGEX_HINT_RE.search(cue):
        return re.search(cue, normalized_text) is not None
    if " " in cue:
        return cue in normalized_text
    return cue in token_set


def extract_text_cues(text: str, cues: Sequence[str] | Iterable[str]) -> dict[str, Any]:
    """Return deterministic cue-matching metadata for literal and regex-like cues."""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return {
            "has_text_cue": False,
            "matched_cues": (),
            "matched_count": 0,
        }

    token_set = tokenize_canonical_text(normalized_text)
    matched_cues: list[str] = []
    for cue in cues:
        normalized_cue = _normalize_cue(cue)
        if not normalized_cue:
            continue
        if _cue_matches(normalized_text, token_set, normalized_cue):
            matched_cues.append(normalized_cue)

    unique_matched_cues = tuple(dict.fromkeys(matched_cues))
    return {
        "has_text_cue": bool(unique_matched_cues),
        "matched_cues": unique_matched_cues,
        "matched_count": len(unique_matched_cues),
    }


__all__ = [
    "extract_text_cues",
]
