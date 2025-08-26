from __future__ import annotations

"""Concept matching utilities.

Provides an Aho-Corasick-based :class:`ConceptMatcher` for concept hit
detection and lightweight helpers for matching arbitrary patterns.
"""

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:  # pragma: no cover - optional dependency
    import ahocorasick  # type: ignore
except Exception:  # pragma: no cover - library is optional
    ahocorasick = None


@dataclass
class ConceptHit:
    """Represents a matched concept span."""

    concept_id: str
    start: int
    end: int


class _Node:
    __slots__ = ("children", "fail", "outputs")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.fail: _Node | None = None
        self.outputs: list[tuple[str, int]] = []


class ConceptMatcher:
    """Match concepts using an Aho-Corasick automaton."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parents[2] / "data" / "concepts"
        else:
            data_dir = Path(data_dir)
        self.root = _Node()
        if data_dir.exists():
            self._load_triggers(data_dir)
            self._build_failure_links()

    def _add(self, trigger: str, concept_id: str) -> None:
        node = self.root
        for ch in trigger:
            node = node.children.setdefault(ch, _Node())
        node.outputs.append((concept_id, len(trigger)))

    def _load_triggers(self, data_dir: Path) -> None:
        for path in sorted(data_dir.glob("*.json")):
            data = json.loads(path.read_text())
            if "id" in data and "phrases" in data:
                concept_id = str(data["id"])
                for phrase in data.get("phrases", []):
                    self._add(str(phrase).lower(), concept_id)
            else:  # mapping of trigger -> concept_id
                for trigger, concept_id in data.items():
                    self._add(str(trigger).lower(), str(concept_id))

    def _build_failure_links(self) -> None:
        queue = deque()
        self.root.fail = self.root
        for child in self.root.children.values():
            child.fail = self.root
            queue.append(child)
        while queue:
            current = queue.popleft()
            for ch, child in current.children.items():
                queue.append(child)
                fail = current.fail
                while fail is not self.root and ch not in fail.children:
                    fail = fail.fail
                child.fail = fail.children.get(ch, self.root)
                child.outputs.extend(child.fail.outputs)

    def match(self, text: str) -> list[ConceptHit]:
        """Return concept hits within the text."""

        hits: list[ConceptHit] = []
        node = self.root
        text = text.lower()
        for i, ch in enumerate(text):
            while ch not in node.children and node is not self.root:
                node = node.fail
            node = node.children.get(ch, self.root)
            for concept_id, length in node.outputs:
                start = i - length + 1
                end = i + 1
                hits.append(ConceptHit(concept_id, start, end))
        return hits


# Load triggers at module import
MATCHER = ConceptMatcher()


@dataclass
class Match:
    """Represents a single pattern match within the text."""

    pattern: str
    start: int
    end: int


@dataclass
class MatchResult:
    """Holds the result of a matching operation."""

    matches: list[Match]
    unmatched_spans: Optional[list[tuple[int, int]]] = None


def match(text: str, patterns: Iterable[str], return_unmatched: bool = False) -> MatchResult:
    """Find occurrences of ``patterns`` within ``text``."""

    pattern_map = {p.lower(): p for p in patterns}
    lowered_patterns = list(pattern_map.keys())
    matches: list[Match] = []

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

    unmatched: Optional[list[tuple[int, int]]] = None
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


__all__ = [
    "ConceptMatcher",
    "ConceptHit",
    "MATCHER",
    "Match",
    "MatchResult",
    "match",
]

