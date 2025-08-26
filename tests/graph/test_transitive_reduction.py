import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.api import serialize_graph
from src.graph.models import LegalGraph, GraphNode, GraphEdge, NodeType, EdgeType


def build_sample_graph() -> LegalGraph:
    g = LegalGraph()
    g.add_node(GraphNode(type=NodeType.CASE, identifier="A"))
    g.add_node(GraphNode(type=NodeType.CASE, identifier="B"))
    g.add_node(GraphNode(type=NodeType.CASE, identifier="C"))
    g.add_edge(GraphEdge(type=EdgeType.CITES, source="A", target="B"))
    g.add_edge(GraphEdge(type=EdgeType.CITES, source="B", target="C"))
    g.add_edge(GraphEdge(type=EdgeType.CITES, source="A", target="C"))
    return g


def build_cyclic_graph() -> LegalGraph:
    g = LegalGraph()
    g.add_node(GraphNode(type=NodeType.CASE, identifier="A"))
    g.add_node(GraphNode(type=NodeType.CASE, identifier="B"))
    g.add_edge(GraphEdge(type=EdgeType.CITES, source="A", target="B"))
    g.add_edge(GraphEdge(type=EdgeType.CITES, source="B", target="A"))
    return g


def test_edges_removed_in_reduction():
    g = build_sample_graph()
    reduced = serialize_graph(g, reduced=True)
    assert not any(
        e["source"] == "A" and e["target"] == "C" for e in reduced["edges"]
    )


def test_edges_reappear_when_not_reduced():
    g = build_sample_graph()
    full = serialize_graph(g, reduced=False)
    assert any(
        e["source"] == "A" and e["target"] == "C" for e in full["edges"]
    )


def test_transitive_reduction_requires_acyclic_graph():
    g = build_cyclic_graph()
    with pytest.raises(ValueError):
        serialize_graph(g, reduced=True)
