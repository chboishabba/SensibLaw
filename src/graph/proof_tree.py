from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Set

from .models import EdgeType, GraphEdge, GraphNode, LegalGraph

ALLOWED_TYPES = {
    EdgeType.PROPOSED_BY,
    EdgeType.EXPLAINS,
    EdgeType.AMENDS,
    EdgeType.INTERPRETED_BY,
}


@dataclass
class ProofTree:
    """A subgraph representing the reasoning around a legal claim."""

    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]

    def to_dict(self) -> Dict[str, object]:
        """Serialise the proof tree into JSON serialisable structure."""

        return {
            "nodes": [
                {
                    "id": n.identifier,
                    "type": n.type.value,
                    "date": n.date.isoformat() if n.date else None,
                    "metadata": n.metadata,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.type.value,
                    "date": e.date.isoformat() if e.date else None,
                    "metadata": e.metadata,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
        }

    def to_dot(self) -> str:
        """Export the proof tree as Graphviz DOT."""

        lines = ["digraph proof_tree {"]
        for node in self.nodes.values():
            label = node.metadata.get("label", node.identifier)
            lines.append(f'  "{node.identifier}" [label="{label}"];')
        for edge in self.edges:
            lines.append(
                f'  "{edge.source}" -> "{edge.target}" '
                f'[label="{edge.type.value}"];'
            )
        lines.append("}")
        return "\n".join(lines)


def expand_proof_tree(
    seed: str, hops: int, as_at: date, *, graph: LegalGraph
) -> ProofTree:
    """Expand a proof tree from ``seed`` up to ``hops`` away.

    Only edges of certain semantic types are traversed. Nodes and edges with a
    ``date`` after ``as_at`` are ignored.
    """

    if seed not in graph.nodes:
        return ProofTree({}, [])

    def node_valid(node: GraphNode) -> bool:
        return node.date is None or node.date <= as_at

    def edge_valid(edge: GraphEdge) -> bool:
        return edge.type in ALLOWED_TYPES and (
            edge.date is None or edge.date <= as_at
        )

    result_nodes: Dict[str, GraphNode] = {}
    result_edges: List[GraphEdge] = []
    visited: Set[str] = set([seed])
    frontier: Set[str] = {seed}

    seed_node = graph.get_node(seed)
    if seed_node and node_valid(seed_node):
        result_nodes[seed] = seed_node

    for _ in range(hops):
        next_frontier: Set[str] = set()
        for node_id in frontier:
            for edge in graph.find_edges(source=node_id):
                if not edge_valid(edge):
                    continue
                target = graph.get_node(edge.target)
                if target is None or not node_valid(target):
                    continue
                result_edges.append(edge)
                if edge.target not in result_nodes:
                    result_nodes[edge.target] = target
                if edge.target not in visited:
                    visited.add(edge.target)
                    next_frontier.add(edge.target)
        frontier = next_frontier
        if not frontier:
            break

    return ProofTree(result_nodes, result_edges)


__all__ = ["ProofTree", "expand_proof_tree"]
