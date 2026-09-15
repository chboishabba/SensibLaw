from __future__ import annotations

from src.pnf.lee_residual_search_gate import (
    lee_search_decision_for_residual,
    project_fact_probe_to_lee_search,
)
from src.pnf.mabo_fact_intake_crosspollination import (
    build_mabo_cross_source_fact_probe,
)


def test_exact_residual_is_shared_structure_and_zero_search_work() -> None:
    decision = lee_search_decision_for_residual({"level": "exact"})

    assert decision.shared_coordinate is True
    assert decision.live_controversy is False
    assert decision.evidence_search_authorised is False
    assert decision.world_truth_claimed is False
    assert decision.party_admission_claimed is False


def test_non_exact_residuals_remain_distinct_live_search_classes() -> None:
    partial = lee_search_decision_for_residual({"level": "partial"})
    no_meet = lee_search_decision_for_residual({"level": "no_typed_meet"})
    contradiction = lee_search_decision_for_residual({"level": "contradiction"})

    assert partial.live_controversy is True
    assert no_meet.live_controversy is True
    assert contradiction.live_controversy is True
    assert partial.search_reason != no_meet.search_reason
    assert no_meet.search_reason != contradiction.search_reason
    assert contradiction.search_reason != partial.search_reason


def test_mabo_cross_source_common_ground_produces_no_evidence_search_work() -> None:
    probe = build_mabo_cross_source_fact_probe()
    projection = project_fact_probe_to_lee_search(probe)

    assert projection["shared_coordinate_count"] == 2
    assert projection["live_controversy_count"] == 0
    assert projection["evidence_search_work_count"] == 0
    assert all(row["residual_level"] == "exact" for row in projection["decisions"])
    assert all(row["shared_coordinate"] is True for row in projection["decisions"])
    assert all(
        row["evidence_search_authorised"] is False
        for row in projection["decisions"]
    )

    boundary = projection["authority_boundary"]
    assert boundary["exact_meet_implies_world_truth"] is False
    assert boundary["exact_meet_implies_party_admission"] is False
    assert boundary["exact_meet_generates_search_work"] is False
    assert boundary["non_exact_residual_generates_fact"] is False
    assert boundary["search_is_residual_indexed"] is True
