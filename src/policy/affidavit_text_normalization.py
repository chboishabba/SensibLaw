"""Shared affidavit text normalization helpers."""
from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "i",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
    "you",
    "your",
}

_TOKEN_NORMALIZATION = {
    "emphasise": "emphasize",
    "emphasised": "emphasized",
    "emphasises": "emphasizes",
    "emphasising": "emphasizing",
    "organisation": "organization",
    "organisations": "organizations",
}

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


@lru_cache(maxsize=32768)
def tokenize_affidavit_text(text: str) -> frozenset[str]:
    tokens = {
        _TOKEN_NORMALIZATION.get(token, token)
        for token in re.findall(r"[A-Za-z0-9']+", text.casefold())
        if len(token) >= 2 and token not in _STOPWORDS
    }
    return frozenset(tokens)


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


@lru_cache(maxsize=16384)
def split_source_text_segments(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
    return parts or [compact]


@lru_cache(maxsize=32768)
def split_source_segment_clauses(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [
        part.strip(" ,;:-")
        for part in re.split(
            r"(?:,\s+(?:and\s+)?so,\s+|,\s+and\s+|,\s+but\s+|,\s+though\s+|,\s+while\s+|;\s+)",
            compact,
        )
        if part.strip(" ,;:-")
    ]
    return parts or [compact]


@lru_cache(maxsize=8192)
def find_numbered_rebuttal_start(text: str) -> int | None:
    compact = str(text or "")
    match = re.search(r"(?<!\d)1\.\s+", compact)
    if not match:
        return None
    return match.start()


@lru_cache(maxsize=16384)
def split_affidavit_sentence_clauses(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [segment.strip(" -") for segment in re.split(r"\s*;\s*", compact) if segment.strip()]
    return parts or [compact]


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
    "find_numbered_rebuttal_start",
    "predicate_focus_tokens",
    "split_affidavit_sentence_clauses",
    "split_affidavit_text",
    "split_source_segment_clauses",
    "split_source_text_segments",
    "tokenize_affidavit_text",
]
