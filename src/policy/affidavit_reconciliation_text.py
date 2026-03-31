"""Shared affidavit reconciliation-text helpers."""
from __future__ import annotations

import re
from typing import Iterable

from src.reporting.structure_report import TextUnit

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
_ENUMERATION_PREFIX_RE = re.compile(r"^\s*\d+(?:[-.]\d+)*[.)]?\s*")
_NUMBERED_LINE_RE = re.compile(r"^\s*\d+(?:[-.]\d+)*[.)]?\s+")


def strip_enumeration_prefix(text: str) -> str:
    return _ENUMERATION_PREFIX_RE.sub("", text).strip()


def tokenize_duplicate_filter_text(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.casefold())
        if len(token) >= 2
    }


def token_overlap_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left & right
    if not shared:
        return 0.0
    return (2.0 * len(shared)) / (len(left) + len(right))


def build_affidavit_duplicate_candidates(affidavit_text: str) -> list[set[str]]:
    candidates: list[set[str]] = []
    for raw_line in affidavit_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = tokenize_duplicate_filter_text(strip_enumeration_prefix(line))
        if tokens:
            candidates.append(tokens)
    return candidates


def is_duplicate_affidavit_unit(
    text: str,
    affidavit_text: str | None = None,
    *,
    affidavit_candidates: Iterable[set[str]] | None = None,
    threshold: float = 0.85,
) -> bool:
    candidates = list(affidavit_candidates or ())
    if not candidates:
        if affidavit_text is None:
            return False
        candidates = build_affidavit_duplicate_candidates(affidavit_text)
    unit_tokens = tokenize_duplicate_filter_text(strip_enumeration_prefix(text))
    return any(token_overlap_similarity(unit_tokens, aff_tokens) >= threshold for aff_tokens in candidates)


def group_contested_response_units(
    response_units: list[TextUnit],
    affidavit_text: str,
    *,
    threshold: float = 0.85,
) -> list[TextUnit]:
    grouped: list[TextUnit] = []
    current_heading: TextUnit | None = None
    current_parts: list[str] = []
    affidavit_candidates = build_affidavit_duplicate_candidates(affidavit_text)
    for unit in response_units:
        text = str(unit.text or "").strip()
        if not text:
            continue
        looks_numbered = bool(_NUMBERED_LINE_RE.match(text))
        is_duplicate_heading = looks_numbered and is_duplicate_affidavit_unit(
            text,
            affidavit_candidates=affidavit_candidates,
            threshold=threshold,
        )
        if is_duplicate_heading:
            if current_heading is not None and current_parts:
                grouped.append(
                    TextUnit(
                        unit_id=f"{current_heading.unit_id}:block",
                        source_id=current_heading.source_id,
                        source_type=current_heading.source_type,
                        text="\n".join(current_parts).strip(),
                    )
                )
            current_heading = unit
            current_parts = [text]
            continue
        if current_heading is not None:
            current_parts.append(text)
            continue
        grouped.append(unit)
    if current_heading is not None and current_parts:
        grouped.append(
            TextUnit(
                unit_id=f"{current_heading.unit_id}:block",
                source_id=current_heading.source_id,
                source_type=current_heading.source_type,
                text="\n".join(current_parts).strip(),
            )
        )
    return grouped


__all__ = [
    "build_affidavit_duplicate_candidates",
    "group_contested_response_units",
    "is_duplicate_affidavit_unit",
    "strip_enumeration_prefix",
    "token_overlap_similarity",
    "tokenize_duplicate_filter_text",
]
