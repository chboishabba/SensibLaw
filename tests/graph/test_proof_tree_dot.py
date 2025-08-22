import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.proof_tree import Edge, Graph, Node, build_subgraph, to_dot


def build_graph() -> Graph:
    g = Graph()
    g.add_node(Node("A", "case", {"label": "A"}, datetime(2020, 1, 1)))
    g.add_node(Node("B", "case", {"label": "B"}, datetime(2020, 1, 1)))
    g.add_node(Node("C", "case", {"label": "C"}, datetime(2020, 1, 1)))
    g.add_edge(
        Edge(
            "A",
            "B",
            "LEADS_TO",
            {"receipt": "r1"},
            datetime(2020, 1, 2),
        )
    )
    g.add_edge(
        Edge(
            "B",
            "C",
            "REJECTS",
            {"receipt": "r2"},
            datetime(2023, 1, 1),
        )
    )
    return g


def test_to_dot_includes_edge_types_and_receipts():
    g = build_graph()
    nodes, edges = build_subgraph(g, ["A"], hops=3)
    dot = to_dot(nodes, edges)
    assert '"A" -> "B" [label="LEADS_TO", receipt="r1"]' in dot
    assert '"B" -> "C" [label="REJECTS", receipt="r2"]' in dot


def test_as_at_filters_edges():
    g = build_graph()
    nodes, edges = build_subgraph(g, ["A"], hops=3, as_at=datetime(2022, 1, 1))
    dot = to_dot(nodes, edges)
    assert 'REJECTS' not in dot
    assert 'LEADS_TO' in dot
