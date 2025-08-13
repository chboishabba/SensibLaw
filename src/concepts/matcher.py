"""Concept matching using an Aho-Corasick automaton."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Iterable


@dataclass
class ConceptHit:
    """A single match for a concept within some text."""

    concept_id: str
    start: int
    end: int


class ConceptMatcher:
    """Match phrases defined in ``data/concepts`` against text."""

    def __init__(self, concept_dir: str | Path = Path("data/concepts")) -> None:
        self._goto: Dict[int, Dict[str, int]] = {}
        self._out: Dict[int, List[Tuple[str, int]]] = {}
        self._fail: Dict[int, int] = {}
        patterns: List[Tuple[str, str]] = []
        concept_path = Path(concept_dir)
        if concept_path.exists():
            for path in sorted(concept_path.glob("*.json")):
                data = json.loads(path.read_text())
                concept_id = data["id"]
                for phrase in data.get("phrases", []):
                    patterns.append((phrase.lower(), concept_id))
        self._build(patterns)

    # Construction -----------------------------------------------------
    def _build(self, patterns: Iterable[Tuple[str, str]]) -> None:
        self._goto = {0: {}}
        self._out = {}
        self._fail = {0: 0}
        state = 1
        for phrase, cid in patterns:
            cur = 0
            for ch in phrase:
                node = self._goto.setdefault(cur, {})
                if ch not in node:
                    node[ch] = state
                    self._goto[state] = {}
                    state += 1
                cur = node[ch]
            self._out.setdefault(cur, []).append((cid, len(phrase)))
        queue = deque()
        for ch, nxt in self._goto[0].items():
            self._fail[nxt] = 0
            queue.append(nxt)
        while queue:
            r = queue.popleft()
            for ch, s in self._goto.get(r, {}).items():
                queue.append(s)
                f = self._fail[r]
                while ch not in self._goto.get(f, {}) and f != 0:
                    f = self._fail[f]
                self._fail[s] = self._goto.get(f, {}).get(ch, 0)
                self._out.setdefault(s, []).extend(self._out.get(self._fail[s], []))

    # Matching ---------------------------------------------------------
    def match(self, text: str) -> List[ConceptHit]:
        """Return all concept matches within *text*."""

        state = 0
        hits: List[ConceptHit] = []
        for idx, ch in enumerate(text.lower()):
            while ch not in self._goto.get(state, {}) and state != 0:
                state = self._fail[state]
            state = self._goto.get(state, {}).get(ch, 0)
            for cid, length in self._out.get(state, []):
                start = idx - length + 1
                end = idx + 1
                hits.append(ConceptHit(cid, start, end))
        return hits

