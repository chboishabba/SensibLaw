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
from .principle_graph import build_principle_graph
from .proof_tree import (
    ProofTree,
    ProofTreeEdge,
    ProofTreeNode,
    Provenance,
    ResultNode,
    ResultTable,
    expand_proof_tree,
)
from .rgcn import (
    RGCNConfig,
    RGCNEpochResult,
    RGCNGraphData,
    RGCNTrainer,
    RGCNTrainingResult,
    RGCNBackendNotAvailableError,
    attach_embeddings,
    export_embeddings,
    legal_graph_to_dgl,
    load_embeddings,
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
    "build_principle_graph",
    "RGCNConfig",
    "RGCNEpochResult",
    "RGCNGraphData",
    "RGCNTrainer",
    "RGCNTrainingResult",
    "RGCNBackendNotAvailableError",
    "attach_embeddings",
    "export_embeddings",
    "legal_graph_to_dgl",
    "load_embeddings",
]

