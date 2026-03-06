from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import os
import re
from typing import Iterable, Iterator, List, Tuple

from src.text.lexeme_normalizer import normalize_lexeme
from src.text.deterministic_legal_tokenizer import (
    LEXEME_TOKENIZER_ID,
    LEXEME_TOKENIZER_VERSION,
    LexemeToken,
    TokenType,
    tokenize_detailed,
    tokenize_with_spans,
)

_LOGGER = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

_LEXEME_TOKENIZER_MODE = os.getenv("ITIR_LEXEME_TOKENIZER_MODE", "deterministic_legal")
_LEXEME_TOKENIZER_SHADOW = os.getenv("ITIR_LEXEME_TOKENIZER_SHADOW", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_LEXEME_TOKENIZER_MODE_ALIAS = {
    "legacy_regex": "legacy_regex",
    "regex": "legacy_regex",
    "spacy": "spacy",
    "deterministic_legal": "deterministic_legal",
    "deterministic_legal_v1": "deterministic_legal",
    "deterministic_legal_v2": "deterministic_legal",
    "legal_lexer_v1": "deterministic_legal",
    "spacy_blank_en": "spacy",
    "deterministic_spacy": "spacy",
    "icu_udpipe": "legacy_regex",
}

_REGEX_TOKENIZER_ID = "regex_legacy_v1"
_REGEX_TOKENIZER_VERSION = "re_unicode_word_symbol_v1"
_WARNED_LEGACY = False


@dataclass(frozen=True, slots=True)
class LexemeOccurrence:
    text: str
    norm_text: str
    kind: str
    start_char: int
    end_char: int
    flags: int


@dataclass(frozen=True, slots=True)
class LexemeTokenizerProfile:
    canonical_tokenizer_id: str
    canonical_tokenizer_version: str
    canonical_mode: str
    shadow_mode: bool
    shadow_tokenizer_id: str | None
    shadow_mismatch_count: int
    canonical_token_count: int


def _normalize_tokenizer_mode(raw: str) -> str:
    return _LEXEME_TOKENIZER_MODE_ALIAS.get((raw or "").strip().lower(), "legacy_regex")


def _iter_regex_tokens(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _TOKEN_PATTERN.finditer(text):
        yield match.group(), match.start(), match.end()


def _iter_spacy_tokens(text: str) -> list[tuple[str, int, int]]:
    try:
        import spacy
    except Exception as exc:  # pragma: no cover - optional dependency path
        _LOGGER.warning("spaCy unavailable for lexeme tokenization; fallback to regex: %s", exc)
        return list(_iter_regex_tokens(text))

    nlp = spacy.blank("en")
    doc = nlp(text)
    return [
        (token.text, token.idx, token.idx + len(token.text))
        for token in doc
        if not token.is_space
    ]


def _spacy_version() -> str:
    try:  # pragma: no cover - optional dependency path
        import spacy
    except Exception:
        return "spacy-missing"
    version = getattr(spacy, "__version__", "unknown")
    return f"spacy_blank_en_{version}"


def _tokenizer_profile_from_mode(mode: str) -> tuple[str, str]:
    if mode == "spacy":
        return "spacy_lexeme_v1", _spacy_version()
    if mode == "deterministic_legal":
        return LEXEME_TOKENIZER_ID, LEXEME_TOKENIZER_VERSION
    return _REGEX_TOKENIZER_ID, _REGEX_TOKENIZER_VERSION


def _collect_token_spans(text: str, mode: str) -> list[tuple[str, int, int]]:
    if mode == "spacy":
        return _iter_spacy_tokens(text)
    if mode == "deterministic_legal":
        return tokenize_with_spans(text)
    return list(_iter_regex_tokens(text))


def _canonicalize_legal_reference(token: LexemeToken):
    def compact_identifier(value: str) -> str:
        out: list[str] = []
        last_underscore = False
        for ch in value.casefold():
            if ch.isalnum():
                out.append(ch)
                last_underscore = False
            else:
                if not last_underscore:
                    out.append("_")
                    last_underscore = True
        compact = "".join(out).strip("_")
        return compact or "unknown"

    def strip_parens(value: str) -> str:
        inner = value.strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]
        return inner.strip().casefold()

    institution_qids = {
        "un": "Q1065",
        "u.n.": "Q1065",
        "uno": "Q1065",
        "united nations": "Q1065",
        "united nations organization": "Q1065",
        "security council": "Q37470",
        "un security council": "Q37470",
        "u.n. security council": "Q37470",
        "unsc": "Q37470",
        "united nations security council": "Q37470",
    }
    court_qids = {
        "international criminal court": "Q47488",
        "icc": "Q47488",
        "icct": "Q47488",
        "international court of justice": "Q7801",
        "icj": "Q7801",
        "world court": "Q7801",
    }

    if token.token_type == TokenType.ACT_REFERENCE:
        return "act_ref", f"act:{compact_identifier(token.text)}"
    if token.token_type == TokenType.CASE_REFERENCE:
        return "case_ref", f"case:{compact_identifier(token.text)}"
    if token.token_type == TokenType.COURT_REFERENCE:
        qid = court_qids.get(token.text.casefold())
        if qid is not None:
            return "court_ref", f"court:wd:{qid}"
        return "court_ref", f"court:{compact_identifier(token.text)}"
    if token.token_type == TokenType.INSTITUTION_REFERENCE:
        qid = institution_qids.get(token.text.casefold())
        if qid is not None:
            return "institution_ref", f"institution:wd:{qid}"
        return "institution_ref", f"institution:{compact_identifier(token.text)}"
    if token.token_type == TokenType.ARTICLE_REFERENCE:
        return "article_ref", f"art:{compact_identifier(token.text.split(None, 1)[1])}"
    if token.token_type == TokenType.INSTRUMENT_REFERENCE:
        return "instrument_ref", f"instrument:{compact_identifier(token.text)}"
    if token.token_type == TokenType.SECTION_REFERENCE:
        parts = token.text.split(None, 1)
        tail = parts[1] if len(parts) > 1 else token.text
        return "section_ref", f"sec:{compact_identifier(tail).replace('_', '')}"
    if token.token_type == TokenType.SUBSECTION_REFERENCE:
        return "subsection_ref", f"subsec:{compact_identifier(strip_parens(token.text))}"
    if token.token_type == TokenType.PARAGRAPH_REFERENCE:
        return "paragraph_ref", f"para:{compact_identifier(strip_parens(token.text))}"
    if token.token_type == TokenType.PART_REFERENCE:
        return "part_ref", f"pt:{compact_identifier(token.text.split(None, 1)[1])}"
    if token.token_type == TokenType.DIVISION_REFERENCE:
        return "division_ref", f"div:{compact_identifier(token.text.split(None, 1)[1])}"
    if token.token_type == TokenType.RULE_REFERENCE:
        return "rule_ref", f"rule:{token.text.split(None, 1)[1].strip().casefold()}"
    if token.token_type == TokenType.SCHEDULE_REFERENCE:
        return "schedule_ref", f"sch:{compact_identifier(token.text.split(None, 1)[1])}"
    if token.token_type == TokenType.CLAUSE_REFERENCE:
        return "clause_ref", f"cl:{compact_identifier(token.text.split(None, 1)[1])}"
    return None


def _token_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_tokenizer_profile() -> dict[str, str]:
    canonical_mode = _normalize_tokenizer_mode(_LEXEME_TOKENIZER_MODE)
    token_id, token_version = _tokenizer_profile_from_mode(canonical_mode)
    shadow_mode = _LEXEME_TOKENIZER_SHADOW
    shadow_id = None
    if shadow_mode:
        shadow_id = "spacy_lexeme_v1" if token_id != "spacy_lexeme_v1" else _REGEX_TOKENIZER_ID
    global _WARNED_LEGACY
    if canonical_mode == "legacy_regex" and not _WARNED_LEGACY:
        _LOGGER.warning("ITIR_LEXEME_TOKENIZER_MODE=legacy_regex set; legacy path should be rollback-only.")
        _WARNED_LEGACY = True

    return {
        "canonical_tokenizer_id": token_id,
        "canonical_tokenizer_version": token_version,
        "canonical_mode": canonical_mode,
        "shadow_mode": str(shadow_mode),
        "shadow_tokenizer_id": shadow_id or "none",
    }


def _compare_profiles(base: list[tuple[str, int, int]], candidate: list[tuple[str, int, int]]) -> int:
    return sum(1 for b, c in zip(base, candidate) if b != c) + abs(len(base) - len(candidate))


def iter_lexeme_occurrences(
    text: str,
    *,
    canonical_mode: str | None = None,
    enable_shadow: bool | None = None,
) -> Iterator[LexemeOccurrence]:
    for occurrence in collect_lexeme_occurrences_with_profile(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )[0]:
        yield occurrence


def collect_lexeme_occurrences(
    text: str,
    *,
    canonical_mode: str | None = None,
    enable_shadow: bool | None = None,
) -> List[LexemeOccurrence]:
    return collect_lexeme_occurrences_with_profile(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )[0]


def collect_lexeme_occurrences_with_profile(
    text: str,
    *,
    canonical_mode: str | None = None,
    enable_shadow: bool | None = None,
) -> tuple[List[LexemeOccurrence], LexemeTokenizerProfile]:
    canonical_mode = _normalize_tokenizer_mode(canonical_mode or _LEXEME_TOKENIZER_MODE)
    shadow_mode = _LEXEME_TOKENIZER_SHADOW if enable_shadow is None else bool(enable_shadow)

    canonical_id, canonical_version = _tokenizer_profile_from_mode(canonical_mode)
    canonical_spans = _collect_token_spans(text, canonical_mode)
    canonical_detailed = tokenize_detailed(text) if canonical_mode == "deterministic_legal" else None

    shadow_tokenizer_id = None
    mismatch_count = 0
    if shadow_mode:
        if canonical_mode == "legacy_regex":
            shadow_mode_name = "spacy"
        elif canonical_mode == "spacy":
            shadow_mode_name = "legacy_regex"
        else:
            shadow_mode_name = "legacy_regex"
        shadow_id, _ = _tokenizer_profile_from_mode(shadow_mode_name)
        shadow_spans = _collect_token_spans(text, shadow_mode_name)
        shadow_tokenizer_id = shadow_id
        mismatch_count = _compare_profiles(canonical_spans, shadow_spans)
        if mismatch_count:
            _LOGGER.warning(
                "lexeme tokenizer shadow mismatch=%s canonical_mode=%s canonical_id=%s shadow_id=%s source_hash=%s",
                mismatch_count,
                canonical_mode,
                canonical_id,
                shadow_id,
                _token_hash(text),
            )

    profile = LexemeTokenizerProfile(
        canonical_tokenizer_id=canonical_id,
        canonical_tokenizer_version=canonical_version,
        canonical_mode=canonical_mode,
        shadow_mode=shadow_mode,
        shadow_tokenizer_id=shadow_tokenizer_id,
        shadow_mismatch_count=mismatch_count,
        canonical_token_count=len(canonical_spans),
    )

    occurrences = []
    for idx, (token_text, start_char, end_char) in enumerate(canonical_spans):
        if canonical_detailed is not None:
            legal_norm = _canonicalize_legal_reference(canonical_detailed[idx])
        else:
            legal_norm = None
        if legal_norm is not None:
            norm_kind, norm_text = legal_norm
            flags = 0
        else:
            norm = normalize_lexeme(token_text)
            norm_kind, norm_text, flags = norm.norm_kind, norm.norm_text, norm.flags
        occurrences.append(
            LexemeOccurrence(
                text=token_text,
                norm_text=norm_text,
                kind=norm_kind,
                start_char=start_char,
                end_char=end_char,
                flags=flags,
            )
        )
    return occurrences, profile


__all__ = [
    "LexemeOccurrence",
    "LexemeTokenizerProfile",
    "collect_lexeme_occurrences",
    "collect_lexeme_occurrences_with_profile",
    "get_tokenizer_profile",
    "iter_lexeme_occurrences",
]
