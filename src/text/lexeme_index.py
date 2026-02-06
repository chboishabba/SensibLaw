"""Lexeme indexing utilities anchored to canonical text spans."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator, List

from src.text.lexeme_normalizer import normalize_lexeme

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class LexemeOccurrence:
    text: str
    norm_text: str
    kind: str
    start_char: int
    end_char: int
    flags: int


def iter_lexeme_occurrences(text: str) -> Iterator[LexemeOccurrence]:
    for match in _TOKEN_PATTERN.finditer(text):
        token = match.group()
        start = match.start()
        end = match.end()
        norm = normalize_lexeme(token)
        yield LexemeOccurrence(
            text=token,
            norm_text=norm.norm_text,
            kind=norm.norm_kind,
            start_char=start,
            end_char=end,
            flags=norm.flags,
        )


def collect_lexeme_occurrences(text: str) -> List[LexemeOccurrence]:
    return list(iter_lexeme_occurrences(text))


__all__ = [
    "LexemeOccurrence",
    "collect_lexeme_occurrences",
    "iter_lexeme_occurrences",
]
