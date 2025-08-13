from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(Enum):
    """Enumeration of supported node types within a legal graph."""

    DOCUMENT = "document"
    PROVISION = "provision"
    PERSON = "person"
    EXTRINSIC = "extrinsic"
    CASE = "case"
    CONCEPT = "concept"


class EdgeType(Enum):
    """Enumeration of supported edge types within a legal graph."""

    CITES = "cites"
    REFERENCES = "references"
    RELATED_TO = "related_to"
    FOLLOWS = "follows"
    DISTINGUISHES = "distinguishes"


@dataclass
class GraphNode:
    """Representation of a node in the legal graph."""

    type: NodeType
    identifier: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    date: Optional[date] = None


@dataclass
class ExtrinsicNode(GraphNode):
    """Node representing extrinsic materials such as parliamentary debates."""

    role: str = ""
    stage: str = ""


@dataclass
class GraphEdge:
    """Representation of a directed edge in the legal graph."""

    type: EdgeType
    source: str
    target: str
    identifier: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    date: Optional[date] = None
    weight: float = 1.0


class LegalGraph:
    """In-memory manager for a simple legal graph."""

    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        """Add or replace a node in the graph."""
        self.nodes[node.identifier] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph.

        Both source and target nodes must already exist.
        """
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError("Both source and target nodes must exist in the graph")
        self.edges.append(edge)

    def get_node(self, identifier: str) -> Optional[GraphNode]:
        """Retrieve a node by its identifier."""
        return self.nodes.get(identifier)

    def find_edges(
        self,
        *,
        source: Optional[str] = None,
        target: Optional[str] = None,
        type: Optional[EdgeType] = None,
        min_weight: Optional[float] = None,
    ) -> List[GraphEdge]:
        """Find edges matching the provided criteria."""
        results = self.edges
        if source is not None:
            results = [e for e in results if e.source == source]
        if target is not None:
            results = [e for e in results if e.target == target]
        if type is not None:
            results = [e for e in results if e.type == type]
        if min_weight is not None:
            results = [e for e in results if e.weight >= min_weight]
        return results


__all__ = [
    "NodeType",
    "EdgeType",
    "GraphNode",
    "ExtrinsicNode",
    "GraphEdge",
    "LegalGraph",
]
