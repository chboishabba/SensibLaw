"""Graph utilities for representing relationships between legal entities."""

from .ingest import compute_weight, ingest_extrinsic
from .models import (
    CaseNode,
    EdgeType,
    ExtrinsicNode,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
)

__all__ = [
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "ExtrinsicNode",
    "CaseNode",
    "LegalGraph",
    "NodeType",
    "ingest_extrinsic",
    "compute_weight",
]
