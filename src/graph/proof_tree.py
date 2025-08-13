from __future__ import annotations

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
        if edge.weight is not None:
            attrs.append(f'weight="{edge.weight}"')
        lines.append(
            f'  "{edge.source}" -> "{edge.target}" [{", ".join(attrs)}];'
        )
    lines.append("}")
    return "\n".join(lines)
