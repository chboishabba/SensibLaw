"""Simple in-memory graph structures and ingestion utilities."""

from .ingest import Graph, ingest_document

__all__ = ["Graph", "ingest_document"]

"""Graph utilities."""

"""Graph utilities for representing relationships between legal entities."""

from .models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType
from .proof_tree import (
    ProofTree,
    ProofTreeEdge,
    ProofTreeNode,
    Provenance,
    ResultNode,
    ResultTable,
)

from .proof_tree import ProofTree, expand_proof_tree
from .ingest import compute_weight, ingest_extrinsic
from .models import EdgeType, ExtrinsicNode, GraphEdge, GraphNode, LegalGraph, NodeType
from .hierarchy import COURT_RANKS, court_weight
from .models import (
    CaseNode,
    EdgeType,
    ExtrinsicNode,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
)
from .api import serialize_graph

__all__ = [
    "EdgeType",
    "GraphEdge",
    "GraphNode",
    "LegalGraph",
    "NodeType",
    "ProofTree",
    "ProofTreeEdge",
    "ProofTreeNode",
    "Provenance",
    "ResultNode",
    "ResultTable",
    "expand_proof_tree",
    "ExtrinsicNode",
    "CaseNode",
    "LegalGraph",
    "NodeType",
    "serialize_graph",
    "ingest_extrinsic",
    "compute_weight",
    "court_weight",
    "COURT_RANKS",
]
