"""Trigger phrase matching utilities.

Provides a :func:`match` function that uses the Aho-Corasick algorithm
(if available) to locate multiple phrases within a body of text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

try:
    import ahocorasick  # type: ignore
except Exception:  # pragma: no cover - library is optional
    ahocorasick = None


@dataclass
class Match:
    """Represents a single pattern match within the text."""

    pattern: str
    start: int
    end: int


@dataclass
class MatchResult:
    """Holds the result of a matching operation."""

    matches: List[Match]
    unmatched_spans: Optional[List[Tuple[int, int]]] = None


def match(text: str, patterns: Iterable[str], return_unmatched: bool = False) -> MatchResult:
    """Find occurrences of ``patterns`` within ``text``.

    Parameters
    ----------
    text:
        Text to search within.
    patterns:
        Iterable of trigger phrases to locate.
    return_unmatched:
        When ``True``, also return spans of the text that were not matched
        by any pattern.

    Returns
    -------
    MatchResult
        Dataclass containing ``matches`` and, optionally, ``unmatched_spans``.
    """

    pattern_map = {p.lower(): p for p in patterns}
    lowered_patterns = list(pattern_map.keys())
    matches: List[Match] = []

    if ahocorasick:
        automaton = ahocorasick.Automaton()
        for pat in lowered_patterns:
            automaton.add_word(pat, pat)
        automaton.make_automaton()
        for end_idx, pat in automaton.iter(text.lower()):
            start_idx = end_idx - len(pat) + 1
            matches.append(Match(pattern=pattern_map[pat], start=start_idx, end=end_idx + 1))
    else:  # fallback naive search
        lower_text = text.lower()
        for pat in lowered_patterns:
            start = 0
            while True:
                idx = lower_text.find(pat, start)
                if idx == -1:
                    break
                matches.append(Match(pattern=pattern_map[pat], start=idx, end=idx + len(pat)))
                start = idx + 1

    matches.sort(key=lambda m: (m.start, m.end))

    unmatched: Optional[List[Tuple[int, int]]] = None
    if return_unmatched:
        unmatched = []
        last_end = 0
        for m in matches:
            if m.start > last_end:
                unmatched.append((last_end, m.start))
            last_end = max(last_end, m.end)
        if last_end < len(text):
            unmatched.append((last_end, len(text)))

    return MatchResult(matches=matches, unmatched_spans=unmatched)


__all__ = ["Match", "MatchResult", "match"]
