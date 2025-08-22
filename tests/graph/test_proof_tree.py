import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph import (
    EdgeType,
    GraphEdge,
    GraphNode,
    LegalGraph,
    NodeType,
    expand_proof_tree,
)
from src.graph.proof_tree import (
    Edge,
    Graph,
    Node,
    ProofTree,
    Provenance,
    ResultNode,
    ResultTable,
    build_subgraph,
    to_dot,
)


# ---------------------------------------------------------------------------
# Result table utilities
# ---------------------------------------------------------------------------


def _build_sample_table() -> ResultTable:
    """Construct a sample ResultTable for testing."""

    f0 = ResultNode(id="F0", label="Root", satisfied=True, children=["F1", "F2"])
    f1 = ResultNode(
        id="F1",
        label="Child 1",
        satisfied=True,
        children=["F3"],
        provenance=Provenance(case="Case A", paragraph="1"),
    )
    f2 = ResultNode(id="F2", label="Child 2", satisfied=False)
    f3 = ResultNode(
        id="F3",
        label="Grandchild",
        satisfied=True,
        provenance=Provenance(statute="Statute B", section="10"),
    )
    results = {n.id: n for n in [f0, f1, f2, f3]}
    return ResultTable(results=results, root_id="F0")


def test_builds_only_satisfied_factors() -> None:
    table = _build_sample_table()
    tree = ProofTree.from_result_table(table)

    assert set(tree.nodes) == {"F0", "F1", "F3"}
    edges = sorted((e.source, e.target) for e in tree.edges)
    assert edges == [("F0", "F1"), ("F1", "F3")]

    edge_map = {(e.source, e.target): e for e in tree.edges}
    edge1 = edge_map[("F0", "F1")]
    edge2 = edge_map[("F1", "F3")]
    assert edge1.provenance.case == "Case A"
    assert edge1.provenance.paragraph == "1"
    assert edge2.provenance.statute == "Statute B"
    assert edge2.provenance.section == "10"


def test_export_formats() -> None:
    table = _build_sample_table()
    tree = ProofTree.from_result_table(table)

    dot = tree.to_dot()
    assert "Case A" in dot
    assert "Statute B" in dot

    data = tree.to_json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    # ensure JSON serialisable
    json.dumps(data)


# ---------------------------------------------------------------------------
# expand_proof_tree tests
# ---------------------------------------------------------------------------


def build_legal_graph() -> LegalGraph:
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


def test_expand_proof_tree_basic() -> None:
    graph = build_legal_graph()
    tree = expand_proof_tree("A", 2, date(2021, 1, 1), graph=graph)
    assert set(tree.nodes.keys()) == {"A", "B", "C"}
    assert len(tree.edges) == 2
    dot = tree.to_dot()
    assert "A" in dot and "B" in dot and "C" in dot


# ---------------------------------------------------------------------------
# build_subgraph and to_dot tests
# ---------------------------------------------------------------------------


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


def test_build_subgraph_hops() -> None:
    g = build_sample_graph()
    nodes, edges = build_subgraph(g, {"A"}, hops=2)
    assert set(nodes.keys()) == {"A", "B", "C"}
    assert {(e.source, e.target) for e in edges} == {("A", "B"), ("B", "C")}


def test_build_subgraph_as_at() -> None:
    g = build_sample_graph()
    nodes, edges = build_subgraph(g, {"A"}, hops=3, as_at=datetime(2021, 6, 1))
    assert set(nodes.keys()) == {"A", "B"}
    assert {(e.source, e.target) for e in edges} == {("A", "B")}


def test_to_dot_output() -> None:
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
