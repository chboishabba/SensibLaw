from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class ConceptHit:
    """Represents a matched concept span."""

    concept_id: str
    start: int
    end: int


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
