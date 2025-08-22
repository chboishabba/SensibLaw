from __future__ import annotations

"""Concept matching using an Aho-Corasick automaton."""

import json
from dataclasses import dataclass
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple, Iterable

from typing import Dict, List, Tuple


@dataclass
class ConceptHit:
    """A single match for a concept within some text."""

    concept_id: str

    """Represents a matched concept span."""

    concept_id: str

"""Trigger phrase matching utilities.

Provides a :func:`match` function that uses the Aho-Corasick algorithm
(if available) to locate multiple phrases within a body of text.
"""

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


class _Node:
    __slots__ = ("children", "fail", "outputs")

    def __init__(self) -> None:
        self.children: Dict[str, _Node] = {}
        self.fail: _Node | None = None
        self.outputs: List[Tuple[str, int]] = []


class ConceptMatcher:
    """Match concepts using an Aho-Corasick automaton."""

    def __init__(self, data_dir: Path | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).resolve().parents[2] / "data" / "concepts"
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
            if isinstance(data, dict):
                for trigger, concept_id in data.items():
                    self._add(trigger.lower(), concept_id)

    def _build_failure_links(self) -> None:
        from collections import deque

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

    def match(self, text: str) -> List[ConceptHit]:
        """Return concept hits within the text."""

        hits: List[ConceptHit] = []
        node = self.root
        text = text.lower()
        for i, ch in enumerate(text):
            while ch not in node.children and node is not self.root:
                node = node.fail
            node = node.children.get(ch, self.root)
            if node.outputs:
                for concept_id, length in node.outputs:
                    start = i - length + 1
                    end = i + 1
                    hits.append(ConceptHit(concept_id, start, end))
        return hits


# Load triggers at module import
MATCHER = ConceptMatcher()

__all__ = ["ConceptMatcher", "ConceptHit", "MATCHER"]

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
