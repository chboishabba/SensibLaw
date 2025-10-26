"""Tests for the R-GCN utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.graph.models import EdgeType, GraphEdge, GraphNode, LegalGraph, NodeType
from src.graph.rgcn import RGCNConfig, RGCNTrainer, legal_graph_to_dgl

torch = pytest.importorskip("torch")
pytest.importorskip("dgl")


def _build_sample_graph() -> LegalGraph:
    graph = LegalGraph()
    graph.add_node(GraphNode(type=NodeType.CASE, identifier="case_a"))
    graph.add_node(GraphNode(type=NodeType.CASE, identifier="case_b"))
    graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier="doc_x"))

    graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="case_a",
            target="case_b",
        )
    )
    graph.add_edge(
        GraphEdge(
            type=EdgeType.REFERENCES,
            source="case_a",
            target="doc_x",
        )
    )
    graph.add_edge(
        GraphEdge(
            type=EdgeType.REFERENCES,
            source="case_b",
            target="doc_x",
        )
    )
    return graph


def test_legal_graph_to_dgl_conversion() -> None:
    graph = _build_sample_graph()
    data = legal_graph_to_dgl(graph)

    assert data.graph.num_nodes() == 3
    assert data.graph.num_edges() == 3
    assert set(data.node_index.keys()) == {"case_a", "case_b", "doc_x"}
    assert set(data.relation_index.keys()) == {EdgeType.CITES, EdgeType.REFERENCES}

    features = data.features
    assert features.shape[0] == 3
    # One-hot for each NodeType plus an in-degree column.
    assert features.shape[1] == len(NodeType) + 1
    assert features.dtype == torch.float32

    in_degrees = data.graph.in_degrees().to(torch.float32)
    assert torch.allclose(features[:, -1], in_degrees)

    relation_ids = data.graph.edata["rel_type"].tolist()
    assert relation_ids.count(data.relation_index[EdgeType.CITES]) == 1
    assert relation_ids.count(data.relation_index[EdgeType.REFERENCES]) == 2


def test_trainer_attaches_embeddings_and_checkpoints(tmp_path: Path) -> None:
    graph = _build_sample_graph()
    # Add an additional node and edge so the validation split receives data.
    graph.add_node(GraphNode(type=NodeType.CASE, identifier="case_c"))
    graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="case_b",
            target="case_c",
        )
    )

    checkpoint_path = tmp_path / "rgcn.pt"
    config = RGCNConfig(
        hidden_dim=8,
        epochs=12,
        num_layers=2,
        validation_ratio=0.25,
        negative_ratio=1,
        checkpoint_path=checkpoint_path,
        metadata_key="rgcn_embedding",
    )

    trainer = RGCNTrainer(graph, config)
    result = trainer.train()

    assert result.embeddings.shape == (len(graph.nodes), config.hidden_dim)
    assert checkpoint_path.exists()
    assert result.best_epoch >= 1

    node = graph.get_node("case_a")
    assert node is not None
    vector = node.metadata.get("rgcn_embedding") if node else None
    assert isinstance(vector, list)
    assert len(vector) == config.hidden_dim
    assert all(isinstance(value, float) for value in vector)
