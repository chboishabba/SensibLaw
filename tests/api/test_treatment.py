import math
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402

from src.api.routes import (  # noqa: E402
    COURT_RANK,
    POSTURE_MATCH_BOOST,
    RELATION_WEIGHT,
    fetch_case_treatment,
    _graph,
)
from src.graph.models import EdgeType, GraphEdge, GraphNode, NodeType  # noqa: E402


def setup_rank_graph() -> str:
    """Create a deterministic graph with rich metadata for ranking tests."""

    _graph.nodes.clear()
    _graph.edges.clear()
    target = "case_target"
    _graph.add_node(
        GraphNode(
            type=NodeType.DOCUMENT,
            identifier=target,
            metadata={"court": "FamCA", "posture": "final"},
            date=date(2020, 1, 1),
        )
    )

    citing_cases = [
        (
            "case_follow",
            {
                "citation": "[2022] HCA 1",
                "title": "Recent High Court authority",
                "court": "HCA",
                "posture": "final",
            },
            {
                "relation": "FOLLOWS",
                "court": "HCA",
                "pinpoint": "¶ 12",
                "factor": "s 60CC(2)(a)",
                "posture": "final",
            },
            date(2022, 1, 1),
        ),
        (
            "case_applies",
            {
                "citation": "[2021] FamCAFC 50",
                "title": "Full Court parenting principles",
                "court": "FAMCAFC",
                "posture": "final",
            },
            {
                "relation": "APPLIES",
                "court": "FAMCAFC",
                "pinpoint": "¶¶ 45-50",
                "factor": "s 60CC(2)(b)",
                "posture": "final",
            },
            date(2021, 6, 1),
        ),
        (
            "case_distinguish",
            {
                "citation": "[2023] Mag 15",
                "title": "Magistrates' view",
                "court": "MAG",
                "posture": "interim",
            },
            {
                "relation": "DISTINGUISHES",
                "court": "MAG",
                "pinpoint": "¶ 5",
                "factor": "s 60CC(3)(c)",
                "posture": "interim",
            },
            date(2023, 3, 1),
        ),
    ]

    for identifier, node_meta, edge_meta, node_date in citing_cases:
        _graph.add_node(
            GraphNode(
                type=NodeType.DOCUMENT,
                identifier=identifier,
                metadata=node_meta,
                date=node_date,
            )
        )
        _graph.add_edge(
            GraphEdge(
                type=EdgeType.CITES,
                source=identifier,
                target=target,
                metadata=edge_meta,
            )
        )

    return target


def test_fetch_case_treatment_scores_and_components():
    target = setup_rank_graph()
    result = fetch_case_treatment(target)

    authorities = result["authorities"]
    assert [a["authority_id"] for a in authorities] == [
        "case_follow",
        "case_applies",
        "case_distinguish",
    ]

    first = authorities[0]
    years = first["years_since"]
    recency = first["components"]["recency_decay"]
    jurisdiction_fit = first["components"]["jurisdiction_fit"]
    expected_score = (
        COURT_RANK["HCA"]
        * RELATION_WEIGHT["FOLLOWS"]
        * recency
        * jurisdiction_fit
        * POSTURE_MATCH_BOOST
    )
    assert math.isclose(first["score"], expected_score, rel_tol=1e-9)
    assert first["pinpoint"] == "¶ 12"
    assert first["factor_alignment"] == "s 60CC(2)(a)"
    assert not first["flag_inapposite"]
    assert math.isclose(first["components"]["recency_decay"], recency, rel_tol=1e-12)
    assert math.isclose(first["components"]["jurisdiction_fit"], jurisdiction_fit, rel_tol=1e-12)
    assert math.isclose(first["components"]["posture_fit"], POSTURE_MATCH_BOOST, rel_tol=1e-12)
    assert math.isclose(first["years_since"], years, rel_tol=1e-12)
    assert "Consider emphasising" in result["what_to_cite_next"]


def test_fetch_case_treatment_flags_and_negative_scores():
    target = setup_rank_graph()
    result = fetch_case_treatment(target)

    negative = next(a for a in result["authorities"] if a["relationship"] == "DISTINGUISHES")
    assert negative["score"] < 0
    assert negative["flag_inapposite"]
    assert negative["pinpoint"] == "¶ 5"


def test_fetch_case_treatment_not_found():
    _graph.nodes.clear()
    _graph.edges.clear()
    with pytest.raises(HTTPException) as exc:
        fetch_case_treatment("missing")
    assert exc.value.status_code == 404

