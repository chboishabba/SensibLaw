"""Shared affidavit reconciliation grouping helpers."""
from __future__ import annotations

import re

from src.reporting.structure_report import TextUnit
from src.policy.affidavit_text_normalization import (
    build_affidavit_duplicate_candidates as _build_affidavit_duplicate_candidates,
    is_duplicate_affidavit_unit as _is_duplicate_affidavit_unit,
    strip_enumeration_prefix as _strip_enumeration_prefix,
    token_overlap_similarity as _token_overlap_similarity,
    tokenize_duplicate_filter_text as _tokenize_duplicate_filter_text,
)

_NUMBERED_LINE_RE = re.compile(r"^\s*\d+(?:[-.]\d+)*[.)]?\s+")


def strip_enumeration_prefix(text: str) -> str:
    return _strip_enumeration_prefix(text)


def tokenize_duplicate_filter_text(text: str) -> set[str]:
    return set(_tokenize_duplicate_filter_text(text))


def token_overlap_similarity(left: set[str], right: set[str]) -> float:
    return _token_overlap_similarity(left, right)


def build_affidavit_duplicate_candidates(affidavit_text: str) -> list[set[str]]:
    return [set(tokens) for tokens in _build_affidavit_duplicate_candidates(affidavit_text)]


def is_duplicate_affidavit_unit(
    text: str,
    affidavit_text: str | None = None,
    *,
    affidavit_candidates: list[set[str]] | None = None,
    threshold: float = 0.85,
) -> bool:
    return _is_duplicate_affidavit_unit(
        text,
        affidavit_text,
        affidavit_candidates=affidavit_candidates,
        threshold=threshold,
    )


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
