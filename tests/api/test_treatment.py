import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from fastapi import HTTPException

from src.api.routes import fetch_case_treatment, _graph, WEIGHT, RANK
from src.graph.models import GraphEdge, GraphNode, EdgeType, NodeType


def setup_graph():
    _graph.nodes.clear()
    _graph.edges.clear()
    target = "case123"
    _graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier=target))

    sources = {
        "caseA": ("followed", "HCA"),
        "caseB": ("followed", "FCA"),
        "caseC": ("distinguished", "NSWCA"),
        "caseD": ("distinguished", "FCA"),
    }
    for src, (relation, court) in sources.items():
        _graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier=src))
        _graph.add_edge(
            GraphEdge(
                type=EdgeType.CITES,
                source=src,
                target=target,
                metadata={"relation": relation, "court": court},
            )
        )

    # Outgoing edge which should be ignored
    _graph.add_node(GraphNode(type=NodeType.DOCUMENT, identifier="other"))
    _graph.add_edge(
        GraphEdge(
            type=EdgeType.CITES,
            source=target,
            target="other",
            metadata={"relation": "followed", "court": "HCA"},
        )
    )
    return target


def test_fetch_case_treatment_aggregates_and_sorts():
    target = setup_graph()
    result = fetch_case_treatment(target)

    followed_total = WEIGHT["followed"] * (RANK["HCA"] + RANK["FCA"])
    distinguished_total = WEIGHT["distinguished"] * (RANK["NSWCA"] + RANK["FCA"])

    assert result["case_id"] == target
    assert result["treatments"] == [
        {"treatment": "followed", "count": 2, "total": followed_total},
        {"treatment": "distinguished", "count": 2, "total": distinguished_total},
    ]


def test_fetch_case_treatment_not_found():
    _graph.nodes.clear()
    _graph.edges.clear()
    with pytest.raises(HTTPException) as exc:
        fetch_case_treatment("missing")
    assert exc.value.status_code == 404
