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
    g.add_node(
        GraphNode(type=NodeType.CASE, identifier="A", metadata={"label": "A"})
    )
    g.add_node(
        GraphNode(type=NodeType.CASE, identifier="B", metadata={"label": "B"})
    )
    g.add_node(
        GraphNode(type=NodeType.CASE, identifier="C", metadata={"label": "C"})
    )
    g.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="A",
            target="B",
            metadata={"note": "AB"},
        )
    )
    g.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="B",
            target="C",
            metadata={"note": "BC"},
        )
    )
    g.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="A",
            target="C",
            metadata={"note": "AC"},
        )
    )
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


def test_cyclic_graph_serializes_without_reduction():
    g = build_cyclic_graph()
    serialised = serialize_graph(g, reduced=False)
    assert len(serialised["edges"]) == 2


def test_transitive_reduction_requires_acyclic_graph():
    g = build_cyclic_graph()
    with pytest.raises(ValueError, match="graph with cycles"):
        serialize_graph(g, reduced=True)


def test_attributes_preserved_after_reduction():
    g = build_sample_graph()
    reduced = serialize_graph(g, reduced=True)
    node_lookup = {n["identifier"]: n for n in reduced["nodes"]}
    assert node_lookup["A"]["metadata"]["label"] == "A"
    edge_lookup = {(e["source"], e["target"]): e for e in reduced["edges"]}
    assert edge_lookup[("A", "B")]["metadata"]["note"] == "AB"
    assert edge_lookup[("B", "C")]["metadata"]["note"] == "BC"
