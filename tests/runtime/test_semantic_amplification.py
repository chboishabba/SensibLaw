from __future__ import annotations

from src.runtime.semantic_amplification import (
    candidate_set_report,
    closure_amplification_report,
    demand_report,
    meet_refinement_report,
)


def _factor(*, state: str, value: str) -> dict[str, object]:
    return {
        "factor_ref": "factor:test",
        "factor_type": "semantic.test",
        "alternatives": [{"value": value}],
        "residuals": [],
        "closure_state": state,
        "metadata": {},
    }


def test_meet_and_refinement_amplification_counts_noops_and_duplicates() -> None:
    prior = _factor(state="open", value="a")
    changed = _factor(state="closed", value="b")
    report = meet_refinement_report(
        (
            {"meet_type_ref": "typing"},
            {"meet_type_ref": "typing"},
            {"meet_type_ref": "constraint"},
        ),
        (
            {"prior_factor": prior, "resulting_factor": prior},
            {"prior_factor": prior, "resulting_factor": changed},
            {"prior_factor": prior, "resulting_factor": changed},
        ),
    )

    assert report["meets_by_type"] == {"constraint": 1, "typing": 2}
    assert report["no_op_refinement_count"] == 1
    assert report["duplicate_resulting_factor_revision_count"] == 1
    assert report["refinements_by_transition"] == {"open->closed": 2, "open->open": 1}


def test_demand_report_finds_reference_and_semantic_duplicates() -> None:
    row = {
        "demand_ref": "demand:1",
        "subject_kind_ref": "semantic.factor",
        "subject_ref": "factor:1",
        "operation_ref": "operation:test",
        "candidate_set_refs": ["set:1"],
        "residual_refs": ["residual:1"],
    }
    report = demand_report((row, row, {**row, "demand_ref": "demand:2"}))

    assert report["demand_count"] == 3
    assert report["duplicate_demand_ref_count"] == 1
    assert report["equivalent_demand_count"] == 2
    assert report["demands_by_subject_kind"] == {"semantic.factor": 3}


def test_candidate_and_closure_reports_expose_amplification_ratios() -> None:
    candidate_report = candidate_set_report(
        {
            "binding_candidate_sets": [
                {"members": []},
                {"members": [{"candidate_factor_ref": "f:1"}]},
                {"member_count": 5, "members": []},
            ]
        }
    )
    closure_report = closure_amplification_report(
        {
            "proposals_examined": 120,
            "proposals_emitted": 30,
            "factor_scans": 200,
            "changed_factors": 20,
        }
    )

    assert candidate_report["candidate_set_size_histogram"] == {
        "0": 1,
        "1": 1,
        "5-16": 1,
    }
    assert candidate_report["candidate_set_max_size"] == 5
    assert closure_report["proposals_examined_per_emitted"] == 4
    assert closure_report["factor_scans_per_changed_factor"] == 10
