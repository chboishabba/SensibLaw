"""Deterministic, no-regex tokenizer for legal structural spans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenType(str, Enum):
    """Token types used by the deterministic legal tokenizer."""

    SECTION_REFERENCE = "SECTION_REFERENCE"
    SUBSECTION_REFERENCE = "SUBSECTION_REFERENCE"
    PARAGRAPH_REFERENCE = "PARAGRAPH_REFERENCE"
    PART_REFERENCE = "PART_REFERENCE"
    DIVISION_REFERENCE = "DIVISION_REFERENCE"
    RULE_REFERENCE = "RULE_REFERENCE"
    SCHEDULE_REFERENCE = "SCHEDULE_REFERENCE"
    CLAUSE_REFERENCE = "CLAUSE_REFERENCE"
    WORD = "WORD"
    NUMBER = "NUMBER"
    PUNCT = "PUNCT"
    ACT_REFERENCE = "ACT_REFERENCE"
    CASE_REFERENCE = "CASE_REFERENCE"


@dataclass(frozen=True, slots=True)
class LexemeToken:
    """Deterministic token output with source spans."""

    token_type: TokenType
    text: str
    start: int
    end: int


def _is_boundary_left(text: str, index: int) -> bool:
    return index == 0 or not (text[index - 1].isalnum() or text[index - 1] in ("_", "-"))


def _consume_whitespace(text: str, start: int) -> int:
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _consume_word(text: str, start: int) -> tuple[str, int, int]:
    i = start
    while i < len(text):
        ch = text[i]
        if ch.isalnum() or ch in {"_", "'"}:
            i += 1
            continue
        break
    return text[start:i], start, i


def _consume_digits(text: str, start: int) -> tuple[str, int, int]:
    i = start
    while i < len(text) and text[i].isdigit():
        i += 1
    return text[start:i], start, i


def _consume_alpha_word(text: str, start: int) -> tuple[str, int, int]:
    i = start
    while i < len(text) and text[i].isalpha():
        i += 1
    return text[start:i], start, i


def _consume_paren_group(text: str, start: int) -> tuple[str, int, int] | None:
    if start >= len(text) or text[start] != "(":
        return None

    i = start + 1
    while i < len(text) and text[i] != ")":
        i += 1
    if i >= len(text):
        return None
    return text[start : i + 1], start, i + 1


def _normalize_keyword(word: str) -> str:
    return word.casefold().rstrip(".")


def _consume_spaced_numberish(
    text: str,
    start: int,
    *,
    allow_dots: bool = False,
    allow_suffix_letters: bool = True,
) -> tuple[str, int, int] | None:
    i = _consume_whitespace(text, start)
    if i >= len(text) or not text[i].isdigit():
        return None
    _, _, end = _consume_digits(text, i)
    if allow_dots:
        while end < len(text) and text[end] == ".":
            next_start = end + 1
            if next_start >= len(text) or not text[next_start].isdigit():
                break
            _, _, end = _consume_digits(text, next_start)
    if allow_suffix_letters:
        while end < len(text) and text[end].isalpha():
            end += 1
    return text[start:end], start, end


def _consume_act_reference(text: str, start: int) -> tuple[str, int, int] | None:
    i = start
    if not _is_boundary_left(text, i):
        return None
    if not text[i].isalpha():
        return None

    cursor = i
    saw_act = False
    words_seen = 0
    while cursor < len(text):
        if text[cursor] == "(":
            group = _consume_paren_group(text, cursor)
            if group is None:
                return None
            _, _, cursor = group
        else:
            word, _, word_end = _consume_word(text, cursor)
            if not word:
                break
            words_seen += 1
            if _normalize_keyword(word) == "act":
                saw_act = True
            cursor = word_end
        space_end = _consume_whitespace(text, cursor)
        if space_end == cursor:
            break
        cursor = space_end
        if saw_act and cursor < len(text) and text[cursor].isdigit():
            break

    if not saw_act or words_seen < 2:
        return None

    year = _consume_spaced_numberish(text, cursor - 1 if cursor > start and text[cursor - 1].isspace() else cursor, allow_dots=False, allow_suffix_letters=False)
    if year is None:
        return None
    _, _, cursor = year

    cursor = _consume_whitespace(text, cursor)
    if cursor < len(text) and text[cursor] == "(":
        group = _consume_paren_group(text, cursor)
        if group is not None:
            _, _, cursor = group

    return text[start:cursor].rstrip(), start, cursor


def _consume_case_reference(text: str, start: int) -> tuple[str, int, int] | None:
    if text[start] != "[":
        return None

    year_end = start + 1
    if year_end >= len(text) or not text[year_end].isdigit():
        return None

    _, year_start, year_end = _consume_digits(text, year_end)
    if year_end <= year_start:
        return None
    if year_end >= len(text) or text[year_end] != "]":
        return None

    i = _consume_whitespace(text, year_end + 1)
    if i >= len(text):
        return None

    # Accept minimal style: [2023] HCA 12
    court_end = i
    while court_end < len(text) and text[court_end].isalpha():
        court_end += 1
    if court_end == i:
        return None
    number_start = _consume_whitespace(text, court_end)
    number, number_start, number_end = _consume_digits(text, number_start)
    if number == "" or i == court_end:
        return None

    return text[start:number_end], start, number_end


def _consume_keyword_reference(
    text: str,
    start: int,
    *,
    keywords: tuple[str, ...],
    token_type: TokenType,
    allow_dots: bool = False,
) -> tuple[str, int, int, TokenType] | None:
    if not _is_boundary_left(text, start):
        return None
    word, _, word_end = _consume_word(text, start)
    if not word or _normalize_keyword(word) not in keywords:
        return None
    span = _consume_spaced_numberish(
        text,
        word_end,
        allow_dots=allow_dots,
        allow_suffix_letters=True,
    )
    if span is None:
        return None
    _, _, span_end = span
    return text[start:span_end], start, span_end, token_type


def _consume_section_reference(text: str, start: int) -> list[tuple[str, int, int, TokenType]] | None:
    if not _is_boundary_left(text, start) or text[start].lower() != "s":
        return None
    i = start + 1
    if i >= len(text) or not text[i].isspace():
        return None

    i = _consume_whitespace(text, i)
    if i >= len(text) or not text[i].isdigit():
        return None

    _, _, section_end = _consume_digits(text, i)
    while section_end < len(text) and text[section_end].isalpha():
        section_end += 1
    section_main = text[i:section_end]
    section_text = f"{text[start]} {section_main}"
    section_span = (section_text, start, section_end)
    tokens: list[tuple[str, int, int, TokenType]] = [(*section_span, TokenType.SECTION_REFERENCE)]

    i = section_end
    while i < len(text):
        i = _consume_whitespace(text, i)
        group = _consume_paren_group(text, i)
        if group is None:
            break
        group_text, group_start, group_end = group
        inner = group_text[1:-1].strip()
        if inner.isdigit():
            tokens.append((group_text, group_start, group_end, TokenType.SUBSECTION_REFERENCE))
        elif len(inner) == 1 and inner.isalpha():
            tokens.append((group_text, group_start, group_end, TokenType.PARAGRAPH_REFERENCE))
        else:
            tokens.append((group_text, group_start, group_end, TokenType.PUNCT))
        i = group_end

    return tokens


def _tokenize_with_no_regex(text: str) -> list[tuple[str, int, int, TokenType]]:
    tokens: list[tuple[str, int, int, TokenType]] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        section_parts = _consume_section_reference(text, i)
        if section_parts is not None:
            tokens.extend(section_parts)
            i = section_parts[-1][2]
            continue

        keyword_reference = (
            _consume_keyword_reference(text, i, keywords=("pt", "part"), token_type=TokenType.PART_REFERENCE)
            or _consume_keyword_reference(text, i, keywords=("div", "division"), token_type=TokenType.DIVISION_REFERENCE)
            or _consume_keyword_reference(text, i, keywords=("r", "rule"), token_type=TokenType.RULE_REFERENCE, allow_dots=True)
            or _consume_keyword_reference(text, i, keywords=("sch", "schedule"), token_type=TokenType.SCHEDULE_REFERENCE)
            or _consume_keyword_reference(text, i, keywords=("cl", "clause"), token_type=TokenType.CLAUSE_REFERENCE)
        )
        if keyword_reference is not None:
            tokens.append(keyword_reference)
            i = keyword_reference[2]
            continue

        act_reference = _consume_act_reference(text, i)
        if act_reference is not None:
            text_span, start, end = act_reference
            tokens.append((text_span, start, end, TokenType.ACT_REFERENCE))
            i = end
            continue

        case_reference = _consume_case_reference(text, i)
        if case_reference is not None:
            text_span, start, end = case_reference
            tokens.append((text_span, start, end, TokenType.CASE_REFERENCE))
            i = end
            continue

        if ch.isdigit():
            text_span, start, end = _consume_digits(text, i)
            token_type = TokenType.NUMBER
        elif ch.isalpha() or ch in {"_"} or ch == "'":
            text_span, start, end = _consume_word(text, i)
            token_type = TokenType.WORD
        else:
            text_span, start, end = ch, i, i + 1
            token_type = TokenType.PUNCT
        tokens.append((text_span, start, end, token_type))
        i = end

    return tokens


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Return deterministic text spans for canonical lexeme extraction."""

    return [(text_span, start, end) for text_span, start, end, _ in _tokenize_with_no_regex(text)]


def tokenize_detailed(
    text: str,
) -> list[LexemeToken]:
    """Return typed canonical-token objects with explicit kinds."""

    return [
        LexemeToken(token_type=token_type, text=text_span, start=start, end=end)
        for text_span, start, end, token_type in _tokenize_with_no_regex(text)
    ]


LEXEME_TOKENIZER_ID = "deterministic_legal_v2"
LEXEME_TOKENIZER_VERSION = "itir_legal_lexer_v2"

__all__ = [
    "LEXEME_TOKENIZER_ID",
    "LEXEME_TOKENIZER_VERSION",
    "LexemeToken",
    "TokenType",
    "tokenize_detailed",
    "tokenize_with_spans",
]
