"""Deterministic cue matching with a numeric semantic hot path.

Human-text matching is retained only as a literal boundary compatibility helper.
Regex cue semantics are intentionally removed: finite semantic cue languages are
compiled to :class:`NumericCueAutomaton` over SymbolIds.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.policy.numeric_cue_automaton import NumericCueAutomaton, NumericCueScan

from .shared_text_normalization import tokenize_canonical_text

_REGEX_META = frozenset(".\\^$*+?{}[]|()")


def _normalize_literal(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def _contains_regex_meta(cue: str) -> bool:
    return any(character in _REGEX_META for character in cue)


def extract_text_cues(text: str, cues: Sequence[str] | Iterable[str]) -> dict[str, Any]:
    """Boundary-only literal cue matcher.

    Regex-like cues now fail closed instead of silently entering semantic
    execution.  Production semantic cue matching should use ``extract_numeric_cues``.
    """
    normalized_text = _normalize_literal(text)
    if not normalized_text:
        return {"has_text_cue": False, "matched_cues": (), "matched_count": 0}

    token_set = tokenize_canonical_text(normalized_text)
    matched: list[str] = []
    for cue in cues:
        normalized_cue = _normalize_literal(cue)
        if not normalized_cue:
            continue
        if _contains_regex_meta(normalized_cue):
            raise ValueError(
                "regex-like semantic cues are unsupported; compile SymbolId patterns"
            )
        if (" " in normalized_cue and normalized_cue in normalized_text) or (
            " " not in normalized_cue and normalized_cue in token_set
        ):
            matched.append(normalized_cue)

    unique = tuple(dict.fromkeys(matched))
    return {"has_text_cue": bool(unique), "matched_cues": unique, "matched_count": len(unique)}


def compile_numeric_cues(
    patterns: Mapping[int, Sequence[int]],
) -> NumericCueAutomaton:
    return NumericCueAutomaton(patterns)


def extract_numeric_cues(
    symbol_ids: Iterable[int], automaton: NumericCueAutomaton
) -> NumericCueScan:
    return automaton.scan(symbol_ids)


__all__ = ["compile_numeric_cues", "extract_numeric_cues", "extract_text_cues"]
