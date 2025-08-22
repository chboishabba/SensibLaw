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

"""Concept phrase matcher using compiled regular expressions.

Provides :class:`ConceptMatcher` which loads phrase→concept mappings and
returns deterministic hit spans when matching against text.  The matcher is
case-insensitive and orders results by appearance in the input string.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


class ConceptMatcher:
    """Match phrases to concept identifiers.

    Parameters
    ----------
    patterns:
        Mapping of trigger phrase to concept identifier.
    """

    def __init__(self, patterns: Dict[str, str]):
        self.patterns = {p.lower(): cid for p, cid in patterns.items()}
        self._group_to_id: Dict[str, str] = {}

        parts: List[str] = []
        # Sort to ensure deterministic group assignment
        for idx, phrase in enumerate(sorted(self.patterns)):
            group = f"g{idx}"
            parts.append(f"(?P<{group}>{re.escape(phrase)})")
            self._group_to_id[group] = self.patterns[phrase]
        pattern = "|".join(parts)
        self._regex = re.compile(pattern, flags=re.IGNORECASE)

    def match(self, text: str) -> List[Tuple[str, Tuple[int, int]]]:
        """Return ordered matches of concepts in *text*.

        Returns
        -------
        List[Tuple[str, Tuple[int, int]]]
            Each tuple contains the concept identifier and the ``(start, end)``
            span of the match in *text*.
        """

        hits: List[Tuple[str, Tuple[int, int]]] = []
        for match in self._regex.finditer(text):
            group = match.lastgroup
            if group:
                concept_id = self._group_to_id[group]
                hits.append((concept_id, match.span()))
        # Ensure deterministic ordering in case of overlaps
        hits.sort(key=lambda h: (h[1][0], h[1][1] - h[1][0], h[0]))
        return hits


def load_patterns(path: Path | str) -> Dict[str, str]:
    """Load phrase→concept mappings from JSON file."""

    p = Path(path)
    data = json.loads(p.read_text())
    return {str(k): str(v) for k, v in data.items()}


__all__ = ["ConceptMatcher", "load_patterns"]
