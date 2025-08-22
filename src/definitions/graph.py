"""Directed graph utilities for term definitions.

This module builds a graph of term identifiers linked by the terms used in
their definitions.  Tarjan's algorithm is used to compute strongly connected
components which are then used to break cycles when expanding definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, DefaultDict
from collections import defaultdict
import json
from pathlib import Path


@dataclass
class Definition:
    """A simple term definition."""

    term: str
    refers: List[str]


class DefinitionGraph:
    """Graph of term definitions with SCC detection."""

    def __init__(self, definitions: Dict[str, List[str]]):
        # Normalise graph ensuring all referenced nodes exist
        self.graph: DefaultDict[str, List[str]] = defaultdict(list)
        for term, refs in definitions.items():
            self.graph[term].extend(refs)
            for ref in refs:
                self.graph.setdefault(ref, [])
        # Pre-compute strongly connected components
        self._build_scc()

    # Tarjan's algorithm implementation
    def _build_scc(self) -> None:
        index = 0
        stack: List[str] = []
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Set[str] = set()
        self._components: List[List[str]] = []
        self._comp_index: Dict[str, int] = {}

        def strongconnect(node: str) -> None:
            nonlocal index
            indices[node] = index
            lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)

            for neigh in self.graph.get(node, []):
                if neigh not in indices:
                    strongconnect(neigh)
                    lowlinks[node] = min(lowlinks[node], lowlinks[neigh])
                elif neigh in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neigh])

            if lowlinks[node] == indices[node]:
                comp: List[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    comp.append(w)
                    if w == node:
                        break
                comp_id = len(self._components)
                for n in comp:
                    self._comp_index[n] = comp_id
                self._components.append(comp)

        for node in list(self.graph.keys()):
            if node not in indices:
                strongconnect(node)

    def expand(self, term: str, depth: int = 1) -> Dict[str, List[str]]:
        """Expand ``term`` definitions up to ``depth`` hops.

        Expansion respects strongly connected components so that nodes within
        the same component are expanded together and only once, preventing
        infinite recursion on cyclic definitions.
        """

        result: Dict[str, List[str]] = {}
        visited: Set[int] = set()

        def _expand_comp(comp_id: int, d: int) -> None:
            if comp_id in visited:
                return
            visited.add(comp_id)
            nodes = self._components[comp_id]
            for node in nodes:
                result[node] = self.graph.get(node, [])
            if d > 0:
                for node in nodes:
                    for dep in self.graph.get(node, []):
                        dep_comp = self._comp_index[dep]
                        if dep_comp not in visited:
                            _expand_comp(dep_comp, d - 1)

        start_comp = self._comp_index.get(term)
        if start_comp is None:
            return {}
        _expand_comp(start_comp, depth)
        return result


def load_default_definitions() -> Dict[str, List[str]]:
    """Load bundled definitions from ``definitions.json`` if present."""

    path = Path(__file__).with_name("definitions.json")
    if path.exists():
        return json.loads(path.read_text())
    return {}
