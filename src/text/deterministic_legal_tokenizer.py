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
    COURT_REFERENCE = "COURT_REFERENCE"
    INSTITUTION_REFERENCE = "INSTITUTION_REFERENCE"
    ARTICLE_REFERENCE = "ARTICLE_REFERENCE"
    INSTRUMENT_REFERENCE = "INSTRUMENT_REFERENCE"


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


def _consume_title_unit(text: str, start: int) -> tuple[str, int, int]:
    word, _, end = _consume_word(text, start)
    if not word:
        return "", start, start
    cursor = end
    if word.isupper():
        while cursor < len(text) and text[cursor] == ".":
            next_start = cursor + 1
            next_word, _, next_end = _consume_alpha_word(text, next_start)
            if len(next_word) != 1 or not next_word.isupper():
                cursor += 1
                break
            cursor = next_end
        if cursor < len(text) and text[cursor] == ".":
            cursor += 1
    return text[start:cursor], start, cursor


def _consume_paren_group(text: str, start: int) -> tuple[str, int, int] | None:
    if start >= len(text) or text[start] != "(":
        return None

    i = start + 1
    while i < len(text) and text[i] != ")":
        i += 1
    if i >= len(text):
        return None
    return text[start : i + 1], start, i + 1


def _consume_optional_reference_paren_groups(text: str, start: int) -> int:
    cursor = start
    while cursor < len(text):
        gap = _consume_whitespace(text, cursor)
        group = _consume_paren_group(text, gap)
        if group is None:
            break
        _, _, cursor = group
    return cursor


def _normalize_keyword(word: str) -> str:
    return word.casefold().rstrip(".")


def _consume_reference_head(text: str, start: int) -> tuple[str, int] | None:
    cursor = _consume_whitespace(text, start)
    word, _, word_end = _consume_word(text, cursor)
    if not word:
        return None
    return _normalize_keyword(word), word_end


def _has_legal_follow_context(text: str, end: int) -> bool:
    cursor = _consume_optional_reference_paren_groups(text, end)
    cursor = _consume_whitespace(text, cursor)
    if cursor >= len(text):
        return True
    if text[cursor] in {".", ",", ";", ":", ")", "]"}:
        return True

    next_head = _consume_reference_head(text, cursor)
    if next_head is None:
        return False
    head, head_end = next_head

    chained_keywords = {
        "s",
        "sec",
        "section",
        "pt",
        "part",
        "div",
        "division",
        "r",
        "rule",
        "sch",
        "schedule",
        "cl",
        "clause",
        "art",
        "article",
    }
    if head in chained_keywords:
        return True

    direct_verbs = {
        "applies",
        "provides",
        "states",
        "requires",
        "allows",
        "bars",
        "permits",
        "means",
        "concerns",
    }
    if head in direct_verbs:
        return True

    if head == "of":
        cursor = _consume_whitespace(text, head_end)
        second_head = _consume_reference_head(text, cursor)
        if second_head is None:
            return False
        second, second_end = second_head
        if second in {"the", "this", "that", "these", "those"}:
            cursor = _consume_whitespace(text, second_end)
            third_head = _consume_reference_head(text, cursor)
            if third_head is None:
                return False
            second = third_head[0]
        legal_nouns = {
            "act",
            "constitution",
            "code",
            "regulation",
            "regulations",
            "rule",
            "rules",
            "schedule",
            "schedules",
            "clause",
            "clauses",
            "section",
            "sections",
            "article",
            "articles",
            "law",
            "laws",
            "statute",
            "statutes",
            "instrument",
            "instruments",
            "treaty",
            "treaties",
            "convention",
            "framework",
            "agreement",
        }
        return second in legal_nouns

    return False


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
    title_connectors = {"of", "and", "the", "for", "to", "on", "in"}
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
            if not saw_act:
                norm_word = _normalize_keyword(word)
                if words_seen == 0:
                    if not word[0].isupper():
                        return None
                elif not (word[0].isupper() or norm_word in title_connectors):
                    break
            words_seen += 1
            if _normalize_keyword(word) == "act":
                saw_act = True
            cursor = word_end
        space_end = _consume_whitespace(text, cursor)
        if space_end == cursor:
            break
        cursor = space_end
        if saw_act and cursor < len(text) and (text[cursor].isdigit() or text[cursor].isalpha()):
            break

    if not saw_act or words_seen < 2:
        return None

    lookahead = cursor
    if lookahead < len(text):
        next_word, _, next_word_end = _consume_word(text, lookahead)
        if _normalize_keyword(next_word) == "of":
            lookahead = _consume_whitespace(text, next_word_end)
    year = _consume_spaced_numberish(text, lookahead, allow_dots=False, allow_suffix_letters=False)
    if year is None:
        cursor = cursor
    else:
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


def _consume_literal_sequence(text: str, start: int, parts: tuple[str, ...]) -> int | None:
    cursor = start
    for idx, part in enumerate(parts):
        if idx > 0:
            cursor = _consume_whitespace(text, cursor)
        end = cursor + len(part)
        if text[cursor:end].casefold() != part.casefold():
            return None
        cursor = end
    return cursor


def _consume_alias_phrase(text: str, start: int, aliases: tuple[str, ...]) -> tuple[str, int, int] | None:
    if not _is_boundary_left(text, start):
        return None
    for alias in aliases:
        end = start + len(alias)
        if text[start:end].casefold() != alias.casefold():
            continue
        if end < len(text) and (text[end].isalnum() or text[end] in {"_", "-"}):
            continue
        return text[start:end], start, end
    return None


def _consume_title_sequence_until_suffix(
    text: str,
    start: int,
    *,
    suffixes: tuple[str, ...],
    connector_words: set[str] | None = None,
) -> tuple[str, int, int] | None:
    if not _is_boundary_left(text, start) or start >= len(text) or not text[start].isalpha():
        return None
    connectors = connector_words or {"of", "the", "and", "for", "to", "on", "in"}
    cursor = start
    words_seen = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor] in {"-", "–", "—", "/"}:
            cursor += 1
        word, _, word_end = _consume_title_unit(text, cursor)
        if not word:
            return None
        norm_word = _normalize_keyword(word)
        if words_seen == 0:
            if not word[0].isupper():
                return None
        elif not (word[0].isupper() or norm_word in connectors):
            return None
        words_seen += 1
        cursor = word_end
        if norm_word in suffixes:
            break
        space_end = _consume_whitespace(text, cursor)
        if space_end == cursor and (cursor >= len(text) or text[cursor] not in {"-", "–", "—", "/"}):
            return None
        if space_end > cursor:
            cursor = space_end
    else:
        return None

    if norm_word not in suffixes or words_seen < 2:
        return None
    return text[start:cursor], start, cursor


def _consume_title_words(text: str, start: int) -> int:
    cursor = start
    consumed_any = False
    while cursor < len(text):
        cursor = _consume_whitespace(text, cursor)
        word, _, word_end = _consume_word(text, cursor)
        if not word:
            break
        if not word[0].isupper() and not word.isdigit():
            break
        consumed_any = True
        cursor = word_end
    return cursor if consumed_any else start


def _consume_court_reference(text: str, start: int) -> tuple[str, int, int] | None:
    if not _is_boundary_left(text, start):
        return None

    seeded = _consume_alias_phrase(
        text,
        start,
        (
            "International Criminal Court",
            "ICC",
            "ICCt",
            "International Court of Justice",
            "ICJ",
            "World Court",
        ),
    )
    if seeded is not None:
        return seeded

    variants = (
        ("u.s. supreme court", ("U.S.", "Supreme", "Court")),
        ("united states supreme court", ("United", "States", "Supreme", "Court")),
        ("united states district court", ("United", "States", "district", "court")),
        ("u.s. district court", ("U.S.", "district", "court")),
        ("united states court of appeals", ("United", "States", "Court", "of", "Appeals")),
        ("u.s. court of appeals", ("U.S.", "Court", "of", "Appeals")),
    )
    for _, parts in variants:
        end = _consume_literal_sequence(text, start, parts)
        if end is None:
            continue
        cursor = end
        phrase = " ".join(part.casefold() for part in parts)
        if phrase.endswith("court of appeals"):
            maybe_for = _consume_whitespace(text, cursor)
            next_end = _consume_literal_sequence(text, maybe_for, ("for", "the"))
            if next_end is not None:
                title_end = _consume_title_words(text, next_end)
                if title_end > next_end:
                    cursor = title_end
        return text[start:cursor], start, cursor
    return None


def _consume_institution_reference(text: str, start: int) -> tuple[str, int, int] | None:
    return _consume_alias_phrase(
        text,
        start,
        (
            "United States Senate",
            "U.S. Senate",
            "US Senate",
            "Senate of the United States",
            "United States House of Representatives",
            "U.S. House of Representatives",
            "US House of Representatives",
            "House of Representatives",
            "United States Department of Defense",
            "U.S. Department of Defense",
            "Department of Defense",
            "Defense Department",
            "Central Intelligence Agency",
            "CIA",
            "Federal Bureau of Investigation",
            "FBI",
            "F.B.I.",
            "United Nations Security Council",
            "UN Security Council",
            "U.N. Security Council",
            "UNSC",
            "Security Council",
            "United Nations",
            "United Nations Organization",
            "UN",
            "U.N.",
            "UNO",
        ),
    )


def _consume_article_reference(text: str, start: int) -> tuple[str, int, int] | None:
    ref = _consume_keyword_reference(
        text,
        start,
        keywords=("art", "article"),
        token_type=TokenType.ARTICLE_REFERENCE,
        allow_dots=False,
    )
    if ref is not None:
        _, ref_start, ref_end, _ = ref
        cursor = _consume_whitespace(text, ref_end)
        if cursor >= len(text):
            return text[ref_start:ref_end], ref_start, ref_end
        if text[cursor] in {".", ",", ";", ":", ")", "]"}:
            return text[ref_start:ref_end], ref_start, ref_end
        next_word, _, next_end = _consume_word(text, cursor)
        if not next_word:
            return text[ref_start:ref_end], ref_start, ref_end
        allowed_followers = {
            "of",
            "under",
            "in",
            "applies",
            "provides",
            "states",
            "requires",
            "allows",
            "bars",
            "permits",
            "means",
        }
        if _normalize_keyword(next_word) in allowed_followers:
            return text[ref_start:ref_end], ref_start, ref_end
    return None


def _consume_instrument_reference(text: str, start: int) -> tuple[str, int, int] | None:
    instrument = _consume_title_sequence_until_suffix(
        text,
        start,
        suffixes=("agreement", "framework", "convention", "resolution"),
    )
    if instrument is not None:
        return instrument
    if text[start : start + 2].casefold() == "un" and _is_boundary_left(text, start):
        end = _consume_whitespace(text, start + 2)
        title_end = _consume_title_words(text, end)
        if title_end > end:
            return text[start:title_end], start, title_end
    return None


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
    if not _has_legal_follow_context(text, span_end):
        return None
    return text[start:span_end], start, span_end, token_type


def _consume_section_reference(text: str, start: int) -> list[tuple[str, int, int, TokenType]] | None:
    if not _is_boundary_left(text, start):
        return None
    keyword, _, keyword_end = _consume_word(text, start)
    keyword_norm = _normalize_keyword(keyword)
    if keyword_norm not in {"s", "sec", "section"}:
        return None
    i = keyword_end
    if i >= len(text) or not text[i].isspace():
        return None

    i = _consume_whitespace(text, i)
    if i >= len(text) or not text[i].isdigit():
        return None

    _, _, section_end = _consume_digits(text, i)
    while section_end < len(text) and text[section_end].isalpha():
        section_end += 1
    section_main = text[i:section_end]
    section_text = f"{text[start:keyword_end]} {section_main}"
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

    if not _has_legal_follow_context(text, tokens[-1][2]):
        return None
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

        article_reference = _consume_article_reference(text, i)
        if article_reference is not None:
            text_span, start, end = article_reference
            tokens.append((text_span, start, end, TokenType.ARTICLE_REFERENCE))
            i = end
            continue

        act_reference = _consume_act_reference(text, i)
        if act_reference is not None:
            text_span, start, end = act_reference
            tokens.append((text_span, start, end, TokenType.ACT_REFERENCE))
            i = end
            continue

        instrument_reference = _consume_instrument_reference(text, i)
        if instrument_reference is not None:
            text_span, start, end = instrument_reference
            tokens.append((text_span, start, end, TokenType.INSTRUMENT_REFERENCE))
            i = end
            continue

        institution_reference = _consume_institution_reference(text, i)
        if institution_reference is not None:
            text_span, start, end = institution_reference
            tokens.append((text_span, start, end, TokenType.INSTITUTION_REFERENCE))
            i = end
            continue

        court_reference = _consume_court_reference(text, i)
        if court_reference is not None:
            text_span, start, end = court_reference
            tokens.append((text_span, start, end, TokenType.COURT_REFERENCE))
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
