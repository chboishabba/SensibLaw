import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph.proof_tree import Edge, Graph, Node, build_subgraph, to_dot


def build_sample_graph() -> Graph:
    g = Graph()
    g.add_node(Node("A", "case", {"label": "A"}, datetime(2020, 1, 1)))
    g.add_node(Node("B", "case", {"label": "B"}, datetime(2021, 1, 1)))
    g.add_node(Node("C", "case", {"label": "C"}, datetime(2022, 1, 1)))
    g.add_node(Node("D", "case", {"label": "D"}, datetime(2023, 1, 1)))

    g.add_edge(Edge("A", "B", "ref", {"label": "A->B"}, datetime(2020, 1, 1)))
    g.add_edge(Edge("B", "C", "ref", {"label": "B->C"}, datetime(2021, 1, 1)))
    g.add_edge(Edge("C", "D", "ref", {"label": "C->D"}, datetime(2022, 1, 1)))
    return g


def test_build_subgraph_hops():
    g = build_sample_graph()
    nodes, edges = build_subgraph(g, {"A"}, hops=2)
    assert set(nodes.keys()) == {"A", "B", "C"}
    assert {(e.source, e.target) for e in edges} == {("A", "B"), ("B", "C")}


def test_build_subgraph_as_at():
    g = build_sample_graph()
    nodes, edges = build_subgraph(g, {"A"}, hops=3, as_at=datetime(2021, 6, 1))
    assert set(nodes.keys()) == {"A", "B"}
    assert {(e.source, e.target) for e in edges} == {("A", "B")}


def test_to_dot_output():
    g = Graph()
    g.add_node(Node("A", "case", {"label": "A"}))
    g.add_node(Node("B", "case", {"label": "B"}))
    g.add_edge(Edge("A", "B", "ref", {"label": "A->B"}))

    nodes, edges = build_subgraph(g, {"A"}, hops=1)
    dot = to_dot(nodes, edges)
    expected = (
        "digraph G {\n"
        '  "A" [label="A"];\n'
        '  "B" [label="B"];\n'
        '  "A" -> "B" [label="A->B"];\n'
        "}"
    )
    assert dot == expected
