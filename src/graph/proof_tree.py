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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class Node:
    """A node in the proof graph."""

    id: str
    type: str
    metadata: Dict[str, object] = field(default_factory=dict)
    date: Optional[datetime] = None


@dataclass
class Edge:
    """A directed edge between two nodes."""

    source: str
    target: str
    type: str
    metadata: Dict[str, object] = field(default_factory=dict)
    date: Optional[datetime] = None
    weight: Optional[float] = None


@dataclass
class Graph:
    """Simple container for nodes and edges."""

    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        """Add or replace a node in the graph."""

        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph.

        The edge is only added if both source and target nodes are present.
        """

        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError("Both source and target nodes must exist in the graph")
        self.edges.append(edge)


def build_subgraph(
    graph: Graph,
    seeds: Iterable[str],
    hops: int,
    as_at: Optional[datetime] = None,
) -> Tuple[Dict[str, Node], List[Edge]]:
    """Traverse the graph breadth-first from seed nodes.

    Parameters
    ----------
    graph:
        Graph to traverse.
    seeds:
        Starting node identifiers.
    hops:
        Maximum number of hops to traverse.
    as_at:
        Optional cut-off date. Nodes or edges with a date later than this are
        ignored.

    Returns
    -------
    tuple of (nodes, edges) that make up the subgraph.
    """

    visited_nodes: Dict[str, Node] = {}
    visited_edges: List[Edge] = []
    edge_keys: Set[Tuple[str, str, str]] = set()

    frontier: Set[str] = set()
    for seed in seeds:
        node = graph.nodes.get(seed)
        if node is None:
            continue
        if as_at and node.date and node.date > as_at:
            continue
        visited_nodes[node.id] = node
        frontier.add(node.id)

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

            for edge in graph.edges:
                if edge.source != node_id:
                    continue
                if as_at and edge.date and edge.date > as_at:
                    continue
                target = graph.nodes.get(edge.target)
                if target is None:
                    continue
                if as_at and target.date and target.date > as_at:
                    continue
                key = (edge.source, edge.target, edge.type)
                if key not in edge_keys:
                    visited_edges.append(edge)
                    edge_keys.add(key)
                if target.id not in visited_nodes:
                    visited_nodes[target.id] = target
                    next_frontier.add(target.id)
        if not next_frontier:
            break
        frontier = next_frontier

    return visited_nodes, visited_edges


def to_dot(nodes: Dict[str, Node], edges: Iterable[Edge]) -> str:
    """Export a set of nodes and edges to Graphviz DOT format."""

    lines = ["digraph G {"]
    for node in nodes.values():
        label = str(node.metadata.get("label", node.id))
        lines.append(f'  "{node.id}" [label="{label}"];')
    for edge in edges:
        label = str(edge.metadata.get("label", edge.type))
        attrs = [f'label="{label}"']
        receipt = edge.metadata.get("receipt")
        if receipt:
            attrs.append(f'receipt="{receipt}"')
        if edge.weight is not None:
            attrs.append(f'weight="{edge.weight}"')
        tooltip = receipt or label or "why is this here?"
        attrs.append(f'tooltip="{tooltip}"')
        lines.append(
            f'  "{edge.source}" -> "{edge.target}" [{", ".join(attrs)}];'
        )
    lines.append("}")
    return "\n".join(lines)
