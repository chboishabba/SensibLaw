from datetime import date
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.graph import (
    EdgeType,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
    expand_proof_tree,
)


def build_sample_graph() -> LegalGraph:
    graph = LegalGraph()
    a = GraphNode(type=NodeType.DOCUMENT, identifier="A", date=date(2020, 1, 1))
    b = GraphNode(type=NodeType.DOCUMENT, identifier="B", date=date(2019, 1, 1))
    c = GraphNode(type=NodeType.DOCUMENT, identifier="C", date=date(2018, 1, 1))
    for n in (a, b, c):
        graph.add_node(n)
    graph.add_edge(
        GraphEdge(
            type=EdgeType.PROPOSED_BY,
            source="A",
            target="B",
            date=date(2019, 1, 1),
        )
    )
    graph.add_edge(
        GraphEdge(
            type=EdgeType.EXPLAINS,
            source="B",
            target="C",
            date=date(2018, 1, 1),
        )
    )
    return graph


def test_expand_proof_tree_basic():
    graph = build_sample_graph()
    tree = expand_proof_tree("A", 2, date(2021, 1, 1), graph=graph)
    assert set(tree.nodes.keys()) == {"A", "B", "C"}
    assert len(tree.edges) == 2
    dot = tree.to_dot()
    assert "A" in dot and "B" in dot and "C" in dot
