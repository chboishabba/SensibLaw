import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.graph import CaseNode, EdgeType, GraphEdge, LegalGraph, NodeType


def test_case_node_and_edges():
    graph = LegalGraph()
    c1 = CaseNode(identifier="case-1", court_rank=1)
    c2 = CaseNode(identifier="case-2", court_rank=2, panel_size=5)
    graph.add_node(c1)
    graph.add_node(c2)

    edge = GraphEdge(
        type=EdgeType.FOLLOWS,
        source=c2.identifier,
        target=c1.identifier,
    )
    graph.add_edge(edge)

    assert c1.type == NodeType.CASE
    matches = graph.find_edges(
        source=c2.identifier, target=c1.identifier, type=EdgeType.FOLLOWS
    )
    assert matches == [edge]

