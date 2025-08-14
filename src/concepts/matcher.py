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
