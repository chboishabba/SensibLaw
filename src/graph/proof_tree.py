from __future__ import annotations

"""Utilities for building proof trees from rule evaluation results.

The :class:`ProofTree` structure is constructed from a :class:`ResultTable`
containing factor evaluation outcomes. Only satisfied factors are included in
the resulting tree. Each edge captures provenance information such as the case
paragraph, statute section, or extrinsic material that supports the factor.

The tree can be exported to DOT or JSON formats for visualisation or further
processing.
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Provenance:
    """Provenance information supporting a factor."""

    case: Optional[str] = None
    paragraph: Optional[str] = None
    statute: Optional[str] = None
    section: Optional[str] = None
    extrinsic: Optional[str] = None


@dataclass
class ResultNode:
    """A single factor evaluation result."""

    id: str
    label: str
    satisfied: bool
    children: List[str] = field(default_factory=list)
    provenance: Optional[Provenance] = None


@dataclass
class ResultTable:
    """Collection of factor evaluation results indexed by identifier."""

    results: Dict[str, ResultNode]
    root_id: str

    def get(self, node_id: str) -> ResultNode:
        return self.results[node_id]


@dataclass
class ProofTreeNode:
    """Node within a proof tree."""

    id: str
    label: str


@dataclass
class ProofTreeEdge:
    """Edge within a proof tree with provenance data."""

    source: str
    target: str
    provenance: Provenance = field(default_factory=Provenance)


class ProofTree:
    """Representation of a proof tree derived from a :class:`ResultTable`."""

    def __init__(self) -> None:
        self.nodes: Dict[str, ProofTreeNode] = {}
        self.edges: List[ProofTreeEdge] = []

    @classmethod
    def from_result_table(cls, table: ResultTable) -> "ProofTree":
        """Build a proof tree from the provided :class:`ResultTable`.

        Only satisfied factors are included in the resulting tree.
        """

        tree = cls()
        visited: Set[str] = set()

        def add_node(result: ResultNode) -> None:
            if result.id in visited or not result.satisfied:
                return
            visited.add(result.id)
            tree.nodes[result.id] = ProofTreeNode(id=result.id, label=result.label)
            for child_id in result.children:
                child = table.get(child_id)
                if not child.satisfied:
                    continue
                add_node(child)
                tree.edges.append(
                    ProofTreeEdge(
                        source=result.id,
                        target=child.id,
                        provenance=child.provenance or Provenance(),
                    )
                )

        root = table.get(table.root_id)
        add_node(root)
        return tree

    # Export helpers -----------------------------------------------------

    def to_dot(self) -> str:
        """Return a Graphviz DOT representation of the proof tree."""

        lines = ["digraph ProofTree {"]
        for node in self.nodes.values():
            lines.append(f'  "{node.id}" [label="{node.label}"];')
        for edge in self.edges:
            label_parts: List[str] = []
            if edge.provenance.case:
                seg = edge.provenance.case
                if edge.provenance.paragraph:
                    seg += f" para {edge.provenance.paragraph}"
                label_parts.append(seg)
            if edge.provenance.statute:
                seg = edge.provenance.statute
                if edge.provenance.section:
                    seg += f" s {edge.provenance.section}"
                label_parts.append(seg)
            if edge.provenance.extrinsic:
                label_parts.append(edge.provenance.extrinsic)
            label = "; ".join(label_parts)
            lines.append(
                f'  "{edge.source}" -> "{edge.target}" [label="{label}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    def to_json(self) -> Dict[str, List[Dict[str, object]]]:
        """Return a JSON-serialisable representation of the proof tree."""

        return {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "provenance": asdict(e.provenance),
                }
                for e in self.edges
            ],
        }


__all__ = [
    "Provenance",
    "ResultNode",
    "ResultTable",
    "ProofTreeNode",
    "ProofTreeEdge",
    "ProofTree",
]
