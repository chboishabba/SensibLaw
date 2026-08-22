from __future__ import annotations

from src.policy.constraint_fixed_point_diagnostics import (
    DIAGNOSTIC_CONTRACT_REF,
    build_constraint_fixed_point_diagnostics,
)


def _factor(ref: str, *, residuals=(), alternatives=()):
    return {
        "factor_ref": ref,
        "factor_type": "semantic.test",
        "alternatives": list(alternatives),
        "constraints": [],
        "residuals": list(residuals),
        "closure_state": "open" if residuals else "locally_closed",
        "metadata": {},
    }


def _graph(*factors):
    return {
        "graph_ref": "pnf:test",
        "document_ref": "document:test",
        "factors": list(factors),
        "constraints": [],
        "relation_refs": [],
        "residuals": [],
    }


def test_diagnostics_reports_semantic_yield_and_fingerprints() -> None:
    before = _graph(_factor("factor:a", residuals=("open",)))
    after = _graph(
        _factor(
            "factor:a",
            alternatives=(
                {
                    "alternative_ref": "alternative:new",
                    "value": {"role": "agent"},
                    "type_ref": "semantic.role_candidate",
                },
            ),
        )
    )
    receipt = build_constraint_fixed_point_diagnostics(
        pnf_graph=before,
        refined_pnf_graph=after,
        constraint_assessments=({"assessment_ref": "assessment:1"},),
        local_meet_plan=({"plan_ref": "plan:1"},),
        typed_meets=({"meet_ref": "meet:1", "state": "compatible_with_refinement"},),
        factor_refinements=(
            {
                "refinement_ref": "refinement:1",
                "added_alternative_refs": ["alternative:new"],
                "rejected_candidate_refs": [],
            },
        ),
        semantic_stage_timing={
            "stage_totals_ms": {
                "constraint_fixed_point": 2_000,
                "postgres_persistence": 300,
            }
        },
    ).to_dict()

    assert receipt["contract_ref"] == DIAGNOSTIC_CONTRACT_REF
    assert receipt["iteration"] == 1
    assert receipt["factors_before"] == 1
    assert receipt["factors_after"] == 1
    assert receipt["factors_rewritten"] == 1
    assert receipt["refinements_applied"] == 1
    assert receipt["resolved_demands"] == 1
    assert receipt["new_accepted_facts"] == 1
    assert receipt["semantic_progress_units"] == 3
    assert receipt["semantic_yield_per_second"] == 1.5
    assert receipt["cumulative_database_read_write_ms"] == 300
    assert receipt["graph_fingerprint_before"].startswith("sha256:")
    assert receipt["graph_fingerprint_after"].startswith("sha256:")
    assert receipt["graph_fingerprint_before"] != receipt["graph_fingerprint_after"]
    assert receipt["classification"] == "legitimate_high_volume_closure"


def test_diagnostics_detects_candidate_explosion() -> None:
    graph = _graph(_factor("factor:a", residuals=("open",)))
    receipt = build_constraint_fixed_point_diagnostics(
        pnf_graph=graph,
        refined_pnf_graph=graph,
        constraint_assessments=tuple(
            {"assessment_ref": f"assessment:{index}"} for index in range(200)
        ),
        local_meet_plan=tuple({"plan_ref": f"plan:{index}"} for index in range(200)),
        typed_meets=tuple(
            {"meet_ref": f"meet:{index}", "state": "rejected"} for index in range(200)
        ),
    ).to_dict()

    assert receipt["constraint_assessments_evaluated"] == 200
    assert receipt["candidate_meets_considered"] == 200
    assert receipt["candidate_meets_accepted"] == 0
    assert receipt["classification"] == "combinatorial_candidate_explosion"


def test_diagnostics_detects_fixed_point_churn() -> None:
    graph = _graph(_factor("factor:a", residuals=("open",)))
    duplicate = {
        "refinement_ref": "refinement:duplicate",
        "added_alternative_refs": [],
        "rejected_candidate_refs": [],
    }
    receipt = build_constraint_fixed_point_diagnostics(
        pnf_graph=graph,
        refined_pnf_graph=graph,
        factor_refinements=(duplicate, duplicate),
    ).to_dict()

    assert receipt["semantic_state_stable"] is True
    assert receipt["refinements_proposed"] == 2
    assert receipt["refinements_deduplicated"] == 1
    assert receipt["semantic_progress_units"] == 0
    assert receipt["classification"] == "fixed_point_churn"
