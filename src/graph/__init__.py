"""Graph utilities and lightweight in-memory structures."""

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
from .tircorder import (
    TiRCorderBuilder,
    applies_to,
    articulates,
    build_tircorder_edges,
    controls,
    has_element,
    interprets,
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
    "ingest_extrinsic",
    "compute_weight",
    "TiRCorderBuilder",
    "build_tircorder_edges",
    "articulates",
    "has_element",
    "applies_to",
    "interprets",
    "controls",
]

