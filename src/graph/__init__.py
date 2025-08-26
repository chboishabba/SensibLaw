"""Graph utilities and lightweight in-memory structures.

This package exposes a minimal set of data structures for representing legal
graphs together with helpers to ingest documents, build proof trees and
serialise the resulting graph structures.
"""

from .api import serialize_graph
from .hierarchy import COURT_RANKS, court_weight
from .ingest import Graph, compute_weight, ingest_document, ingest_extrinsic
from .models import (
    CaseNode,
    EdgeType,
    ExtrinsicNode,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
)
from .proof_tree import (
    ProofTree,
    ProofTreeEdge,
    ProofTreeNode,
    Provenance,
    ResultNode,
    ResultTable,
    expand_proof_tree,
)

__all__ = [
    "Graph",
    "ingest_document",
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
    "serialize_graph",
    "ingest_extrinsic",
    "compute_weight",
    "court_weight",
    "COURT_RANKS",
]

