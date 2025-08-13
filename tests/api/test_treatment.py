import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from fastapi import HTTPException

from src.api.routes import fetch_case_treatment, _graph
from src.graph.models import GraphEdge, GraphNode, EdgeType, NodeType


def setup_graph():
    _graph.nodes.clear()
    _graph.edges.clear()
    target = "case123"
    _graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier=target))
    for src in ["caseA", "caseB", "caseC"]:
        _graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier=src))
    _graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="caseA",
            target=target,
            weight=0.5,
            metadata={"treatment": "distinguished", "citation": "A v B"},
        )
    )
    _graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="caseB",
            target=target,
            weight=0.8,
            metadata={"treatment": "followed", "citation": "B v C"},
        )
    )
    _graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source="caseC",
            target=target,
            weight=0.9,
            metadata={"treatment": "followed", "citation": "C v D"},
        )
    )
    return target


def test_fetch_case_treatment_aggregates_and_sorts():
    target = setup_graph()
    result = fetch_case_treatment(target)
    assert result["case_id"] == target
    assert result["treatments"] == [
        {
            "treatment": "followed",
            "count": 2,
            "citation": "C v D",
            "weight": 0.9,
        },
        {
            "treatment": "distinguished",
            "count": 1,
            "citation": "A v B",
            "weight": 0.5,
        },
    ]


def test_fetch_case_treatment_not_found():
    _graph.nodes.clear()
    _graph.edges.clear()
    try:
        fetch_case_treatment("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        assert False, "Expected HTTPException for missing case"
