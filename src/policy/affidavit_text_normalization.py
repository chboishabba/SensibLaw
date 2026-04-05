"""Affidavit text normalization and contested-text helpers."""
from __future__ import annotations

from functools import lru_cache
import re
from typing import Any
from src.text.shared_text_normalization import (
    split_semicolon_clauses,
    split_text_clauses,
    split_text_segments,
    strip_enumeration_prefix,
    tokenize_canonical_text,
)

_MONTH_TOKENS = frozenset(
    month.casefold()
    for month in (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
)

_SHORT_PREDICATE_TOKENS = frozenset({"epoa"})

_PREDICATE_NEUTRAL_TOKENS = frozenset(
    {
        "could",
        "couldn't",
        "couldnt",
        "couldn",
        "didn",
        "doesn",
        "don",
        "hadn",
        "hasn",
        "haven",
        "isn",
        "must",
        "shouldn",
        "should",
        "shouldn't",
        "shouldnt",
        "wasn",
        "weren",
        "will",
        "won",
        "would",
        "wouldn",
    }
)

tokenize_affidavit_text = tokenize_canonical_text


@lru_cache(maxsize=32768)
def tokenize_duplicate_filter_text(text: str) -> frozenset[str]:
    return frozenset(tokenize_affidavit_text(strip_enumeration_prefix(text)))


def token_overlap_similarity(left: set[str] | frozenset[str], right: set[str] | frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    if not shared:
        return 0.0
    return (2.0 * len(shared)) / (len(left) + len(right))


def build_affidavit_duplicate_candidates(affidavit_text: str) -> list[frozenset[str]]:
    candidates: list[frozenset[str]] = []
    for raw_line in str(affidavit_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = tokenize_duplicate_filter_text(line)
        if tokens:
            candidates.append(tokens)
    return candidates


def is_duplicate_affidavit_unit(
    text: str,
    affidavit_text: str | None = None,
    *,
    affidavit_candidates: list[set[str] | frozenset[str]] | None = None,
    threshold: float = 0.85,
) -> bool:
    candidates = list(affidavit_candidates or ())
    if not candidates:
        if affidavit_text is None:
            return False
        candidates = build_affidavit_duplicate_candidates(affidavit_text)
    unit_tokens = tokenize_duplicate_filter_text(text)
    return any(token_overlap_similarity(unit_tokens, aff_tokens) >= threshold for aff_tokens in candidates)


def is_duplicate_response_excerpt(proposition_text: str, excerpt_text: str) -> bool:
    proposition_tokens = tokenize_affidavit_text(proposition_text)
    excerpt_tokens = tokenize_affidavit_text(excerpt_text)
    if not proposition_tokens or not excerpt_tokens:
        return False
    shared_ratio = len(proposition_tokens & excerpt_tokens) / len(proposition_tokens)
    return shared_ratio >= 0.85


@lru_cache(maxsize=32768)
def predicate_focus_tokens(text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in tokenize_affidavit_text(text)
        if token not in _MONTH_TOKENS
        and token not in _PREDICATE_NEUTRAL_TOKENS
        and not token.isdigit()
        and (len(token) >= 5 or token in _SHORT_PREDICATE_TOKENS)
    )


split_source_text_segments = split_text_segments
split_source_segment_clauses = split_text_clauses


@lru_cache(maxsize=8192)
def find_numbered_rebuttal_start(text: str) -> int | None:
    compact = str(text or "")
    match = re.search(r"(?<!\d)1\.\s+", compact)
    if not match:
        return None
    return match.start()


split_affidavit_sentence_clauses = split_semicolon_clauses


def split_affidavit_text(text: str) -> list[dict[str, Any]]:
    propositions: list[dict[str, Any]] = []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    for paragraph_index, paragraph in enumerate(paragraphs, start=1):
        sentence_parts = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
            if sentence.strip()
        ]
        if not sentence_parts:
            sentence_parts = [paragraph]
        decomposed_parts: list[str] = []
        for sentence in sentence_parts:
            decomposed_parts.extend(split_affidavit_sentence_clauses(sentence))
        if not decomposed_parts:
            decomposed_parts = sentence_parts
        for sentence_index, sentence in enumerate(decomposed_parts, start=1):
            proposition_id = f"aff-prop:p{paragraph_index}-s{sentence_index}"
            propositions.append(
                {
                    "proposition_id": proposition_id,
                    "paragraph_id": f"p{paragraph_index}",
                    "paragraph_order": paragraph_index,
                    "sentence_order": sentence_index,
                    "text": sentence,
                    "tokens": sorted(tokenize_affidavit_text(sentence)),
                }
            )
    return propositions


__all__ = [
    "build_affidavit_duplicate_candidates",
    "find_numbered_rebuttal_start",
    "is_duplicate_affidavit_unit",
    "is_duplicate_response_excerpt",
    "predicate_focus_tokens",
    "split_affidavit_sentence_clauses",
    "split_affidavit_text",
    "split_source_segment_clauses",
    "split_source_text_segments",
    "strip_enumeration_prefix",
    "token_overlap_similarity",
    "tokenize_duplicate_filter_text",
    "tokenize_affidavit_text",
]
