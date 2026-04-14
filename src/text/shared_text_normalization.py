"""Shared pre-semantic text normalization helpers."""
from __future__ import annotations

from functools import lru_cache
import re

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

_ENUMERATION_PREFIX_RE = re.compile(r"^\s*\d+(?:[-.]\d+)*[.)]?\s*")


@lru_cache(maxsize=32768)
def tokenize_canonical_text(text: str) -> frozenset[str]:
    tokens = {
        _TOKEN_NORMALIZATION.get(token, token)
        for token in re.findall(r"[A-Za-z0-9']+", text.casefold())
        if len(token) >= 2 and token not in _STOPWORDS
    }
    return frozenset(tokens)


def strip_enumeration_prefix(text: str) -> str:
    return _ENUMERATION_PREFIX_RE.sub("", str(text or "")).strip()


@lru_cache(maxsize=16384)
def split_text_segments(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [segment.strip(" -") for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
    return parts or [compact]


@lru_cache(maxsize=32768)
def split_text_clauses(text: str) -> list[str]:
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


@lru_cache(maxsize=16384)
def split_semicolon_clauses(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = [segment.strip(" -") for segment in re.split(r"\s*;\s*", compact) if segment.strip()]
    return parts or [compact]


__all__ = [
    "split_semicolon_clauses",
    "split_text_clauses",
    "split_text_segments",
    "strip_enumeration_prefix",
    "tokenize_canonical_text",
]
