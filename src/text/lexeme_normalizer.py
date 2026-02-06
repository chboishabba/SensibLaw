from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import IntFlag
from typing import Tuple


class LexemeFlags(IntFlag):
    NONE = 0

    SURF_ALL_UPPER = 1 << 0
    SURF_ALL_LOWER = 1 << 1
    SURF_TITLE = 1 << 2
    SURF_MIXED_CASE = 1 << 3

    HAS_NON_ASCII = 1 << 4
    HAS_LETTER = 1 << 5
    HAS_DIGIT = 1 << 6
    HAS_PUNCT = 1 << 7
    HAS_SYMBOL = 1 << 8

    HAS_REPLACEMENT_CHAR = 1 << 9
    HAS_ZERO_WIDTH = 1 << 10


@dataclass(frozen=True, slots=True)
class LexemeNorm:
    norm_text: str
    norm_kind: str
    flags: int


_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}
_PUNCT_CATS = {"Pc", "Pd", "Pe", "Pf", "Pi", "Po", "Ps"}
_SYMBOL_CATS = {"Sc", "Sk", "Sm", "So"}


def _case_flags(surface: str) -> int:
    letters = [ch for ch in surface if ch.isalpha()]
    if not letters:
        return 0

    if all(ch.isupper() for ch in letters):
        return int(LexemeFlags.SURF_ALL_UPPER)
    if all(ch.islower() for ch in letters):
        return int(LexemeFlags.SURF_ALL_LOWER)

    first_index = next((i for i, ch in enumerate(surface) if ch.isalpha()), None)
    if first_index is not None:
        first = surface[first_index]
        rest = [ch for ch in surface[first_index + 1 :] if ch.isalpha()]
        if first.isupper() and all(ch.islower() for ch in rest):
            return int(LexemeFlags.SURF_TITLE)

    return int(LexemeFlags.SURF_MIXED_CASE)


def _kind_and_content_flags(s: str) -> Tuple[str, int]:
    if s == "":
        return "other", int(LexemeFlags.NONE)
    if s.isspace():
        return "ws", int(LexemeFlags.NONE)

    flags = 0

    if any(ord(ch) > 127 for ch in s):
        flags |= int(LexemeFlags.HAS_NON_ASCII)

    if "�" in s:
        flags |= int(LexemeFlags.HAS_REPLACEMENT_CHAR)
    if any(ch in _ZERO_WIDTH for ch in s):
        flags |= int(LexemeFlags.HAS_ZERO_WIDTH)

    if any(ch.isalpha() for ch in s):
        flags |= int(LexemeFlags.HAS_LETTER)
    if any(ch.isdigit() for ch in s):
        flags |= int(LexemeFlags.HAS_DIGIT)

    cats = [unicodedata.category(ch) for ch in s if not ch.isspace()]
    if cats and all(c == "Nd" for c in cats):
        return "number", flags
    if cats and all(c in _PUNCT_CATS for c in cats):
        flags |= int(LexemeFlags.HAS_PUNCT)
        return "punct", flags
    if cats and all(c in _SYMBOL_CATS for c in cats):
        flags |= int(LexemeFlags.HAS_SYMBOL)
        return "symbol", flags

    if flags & int(LexemeFlags.HAS_LETTER):
        return "word", flags
    if flags & int(LexemeFlags.HAS_DIGIT):
        return "number", flags

    return "other", flags


def normalize_lexeme(surface: str) -> LexemeNorm:
    flags = _case_flags(surface)
    s = unicodedata.normalize("NFKC", surface)
    kind, content_flags = _kind_and_content_flags(s)
    flags |= content_flags

    if kind == "ws":
        norm = " "
    elif kind in ("punct", "symbol"):
        norm = s
    else:
        norm = s.casefold()

    return LexemeNorm(norm_text=norm, norm_kind=kind, flags=flags)


__all__ = ["LexemeFlags", "LexemeNorm", "normalize_lexeme"]
