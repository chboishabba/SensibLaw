"""Lexeme indexing utilities anchored to canonical text spans."""
from __future__ import annotations

from dataclasses import dataclass
import re
import string
import unicodedata
from typing import Iterable, Iterator, List

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

FLAG_ALL_CAPS = 1 << 0
FLAG_TITLE_CASE = 1 << 1
FLAG_MIXED_CASE = 1 << 2
FLAG_HAS_DIGIT = 1 << 3
FLAG_NON_ASCII = 1 << 4


@dataclass(frozen=True, slots=True)
class LexemeOccurrence:
    text: str
    norm_text: str
    kind: str
    start_char: int
    end_char: int
    flags: int


def _normalise_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _classify_kind(token: str) -> str:
    if token.isdigit():
        return "number"
    if token.isalpha():
        return "word"
    if all(ch in string.punctuation for ch in token):
        return "punct"
    if any(ch.isalnum() for ch in token):
        return "symbol"
    return "other"


def _flags_for_token(token: str) -> int:
    flags = 0
    if token and token.isupper():
        flags |= FLAG_ALL_CAPS
    elif token and token.istitle():
        flags |= FLAG_TITLE_CASE
    elif token and any(ch.isupper() for ch in token) and any(ch.islower() for ch in token):
        flags |= FLAG_MIXED_CASE
    if any(ch.isdigit() for ch in token):
        flags |= FLAG_HAS_DIGIT
    if any(ord(ch) > 127 for ch in token):
        flags |= FLAG_NON_ASCII
    return flags


def iter_lexeme_occurrences(text: str) -> Iterator[LexemeOccurrence]:
    for match in _TOKEN_PATTERN.finditer(text):
        token = match.group()
        start = match.start()
        end = match.end()
        norm = _normalise_text(token)
        kind = _classify_kind(norm)
        flags = _flags_for_token(token)
        yield LexemeOccurrence(
            text=token,
            norm_text=norm,
            kind=kind,
            start_char=start,
            end_char=end,
            flags=flags,
        )


def collect_lexeme_occurrences(text: str) -> List[LexemeOccurrence]:
    return list(iter_lexeme_occurrences(text))


__all__ = [
    "LexemeOccurrence",
    "collect_lexeme_occurrences",
    "iter_lexeme_occurrences",
    "FLAG_ALL_CAPS",
    "FLAG_TITLE_CASE",
    "FLAG_MIXED_CASE",
    "FLAG_HAS_DIGIT",
    "FLAG_NON_ASCII",
]
