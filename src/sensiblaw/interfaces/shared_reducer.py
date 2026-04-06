from __future__ import annotations

"""Supported cross-product access to SL canonical lexer/reducer outputs."""

import hashlib

try:
    from src.text.deterministic_legal_tokenizer import (
        LexemeToken,
        tokenize_detailed,
        tokenize_with_spans,
    )
    from src.text.lexeme_index import (
        LexemeOccurrence,
        LexemeTokenizerProfile,
        collect_lexeme_occurrences,
        collect_lexeme_occurrences_with_profile,
        get_tokenizer_profile,
    )
    from src.text.operational_structure import StructureOccurrence
    from src.text.structure_index import collect_structure_occurrences
except ModuleNotFoundError:  # pragma: no cover - cross-product import path
    from text.deterministic_legal_tokenizer import (
        LexemeToken,
        tokenize_detailed,
        tokenize_with_spans,
    )
    from text.lexeme_index import (
        LexemeOccurrence,
        LexemeTokenizerProfile,
        collect_lexeme_occurrences,
        collect_lexeme_occurrences_with_profile,
        get_tokenizer_profile,
    )
    from text.operational_structure import StructureOccurrence
    from text.structure_index import collect_structure_occurrences


def get_canonical_tokenizer_profile() -> dict[str, str]:
    """Return the current SL canonical tokenizer profile for cross-product consumers."""

    return get_tokenizer_profile()


def get_canonical_tokenizer_profile_receipt() -> dict[str, str]:
    """Return a bounded receipt for the current tokenizer profile."""

    profile = get_tokenizer_profile()
    profile_items = sorted(profile.items())
    profile_seed = "|".join(f"{key}={value}" for key, value in profile_items)
    return {
        "profile_id": hashlib.sha256(profile_seed.encode("utf-8")).hexdigest()[:16],
        "canonical_tokenizer_id": profile["canonical_tokenizer_id"],
        "canonical_tokenizer_version": profile["canonical_tokenizer_version"],
        "canonical_mode": profile["canonical_mode"],
    }


def collect_canonical_lexeme_occurrences(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> list[LexemeOccurrence]:
    """Collect canonical lexeme occurrences using the SL-owned reducer contract."""

    return collect_lexeme_occurrences(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )


def collect_canonical_lexeme_occurrences_with_profile(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> tuple[list[LexemeOccurrence], LexemeTokenizerProfile]:
    """Collect canonical lexeme occurrences together with the tokenizer profile."""

    return collect_lexeme_occurrences_with_profile(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )


def collect_canonical_lexeme_refs(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    enable_shadow: bool | None = None,
) -> list[dict[str, int | str]]:
    """Collect bounded opaque refs for SL-owned lexeme occurrences."""

    occurrences = collect_canonical_lexeme_occurrences(
        text,
        canonical_mode=canonical_mode,
        enable_shadow=enable_shadow,
    )
    refs: list[dict[str, int | str]] = []
    for occurrence in occurrences:
        occurrence_seed = "|".join(
            (
                occurrence.kind,
                occurrence.norm_text,
                str(occurrence.start_char),
                str(occurrence.end_char),
                str(occurrence.flags),
            )
        )
        refs.append(
            {
                "occurrence_id": hashlib.sha256(occurrence_seed.encode("utf-8")).hexdigest()[:16],
                "kind": occurrence.kind,
                "span_start": occurrence.start_char,
                "span_end": occurrence.end_char,
            }
        )
    return refs


def collect_canonical_structure_occurrences(
    text: str,
    *,
    canonical_mode: str = "deterministic_legal",
    include_legal: bool = True,
    include_operational: bool = True,
) -> list[StructureOccurrence]:
    """Collect the combined SL legal + operational structure occurrence stream."""

    return collect_structure_occurrences(
        text,
        canonical_mode=canonical_mode,
        include_legal=include_legal,
        include_operational=include_operational,
    )


def tokenize_canonical_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Expose SL canonical span tokenization as a supported adapter call."""

    return tokenize_with_spans(text)


def tokenize_canonical_detailed(text: str) -> list[LexemeToken]:
    """Expose SL canonical detailed tokenization as a supported adapter call."""

    return tokenize_detailed(text)


__all__ = [
    "LexemeOccurrence",
    "LexemeTokenizerProfile",
    "LexemeToken",
    "StructureOccurrence",
    "collect_canonical_lexeme_refs",
    "collect_canonical_lexeme_occurrences",
    "collect_canonical_lexeme_occurrences_with_profile",
    "collect_canonical_structure_occurrences",
    "get_canonical_tokenizer_profile",
    "get_canonical_tokenizer_profile_receipt",
    "tokenize_canonical_detailed",
    "tokenize_canonical_with_spans",
]
