from __future__ import annotations

import json
from pathlib import Path

from src.ontology.wikidata_nat_automation_graduation import (
    AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_QUEUE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
    build_nat_claim_convergence_report,
    build_nat_automation_graduation_batch_report,
    build_nat_automation_graduation_evidence_report,
    build_nat_automation_graduation_governance_index,
    build_nat_automation_graduation_governance_summary,
    build_nat_automation_graduation_report,
    build_nat_confirmation_intake_contract,
    build_nat_confirmation_intake_report,
    build_nat_confirmation_follow_queue,
    build_nat_gate_b_proposal_batches_from_verification_runs,
    evaluate_nat_automation_promotion,
)


def _load_graduation_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_automation_graduation_criteria_20260402.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_cohort_a_gate_b_candidate_evidence_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_evidence_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_cohort_a_gate_b_candidate_evidence_ready_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_evidence_ready_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_cohort_a_gate_b_candidate_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_run_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_seed_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_seed_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_verification_run_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_claim_convergence_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_claim_convergence_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_confirmation_queue_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_confirmation_queue_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_confirmation_intake_contract_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_confirmation_intake_contract_20260403.json"
        ).read_text(encoding="utf-8")
    )


def test_evaluator_approves_gate_a_when_all_requirements_are_met() -> None:
    criteria = _load_graduation_fixture()
    proposal = {
        "gate_id": "A",
        "from_level": 0,
        "to_level": 1,
        "gate_families_passed": criteria["gate_families_required"],
        "evidence_signals": [
            "reviewer_packets_for_representative_split_shapes",
            "bounded_follow_depth_present_and_fail_closed",
            "split_plan_verification_on_representative_reviewed_plans",
            "uncertainty_flags_preserved",
        ],
        "risk_signals": [],
        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
        "recommendation": "promote",
    }

    result = evaluate_nat_automation_promotion(criteria, proposal)

    assert result["schema_version"] == AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION
    assert result["status"] == "approved"
    assert result["decision"] == "promote"
    assert result["promotion_allowed"] is True
    assert result["failed_checks"] == []


def test_evaluator_rejects_when_blocked_signal_is_triggered() -> None:
    criteria = _load_graduation_fixture()
    proposal = {
        "gate_id": "B",
        "from_level": 1,
        "to_level": 2,
        "gate_families_passed": criteria["gate_families_required"],
        "evidence_signals": [
            "repeated_family_scoped_direct_safe_behavior",
            "stable_after_state_verification_across_repeated_tranches",
            "false_positive_rate_within_family_budget",
            "hold_and_abstain_paths_effective",
        ],
        "risk_signals": ["repeated_tranches_revert_to_split_required_majority"],
        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
        "recommendation": "promote",
    }

    result = evaluate_nat_automation_promotion(criteria, proposal)

    assert result["status"] == "rejected"
    assert result["decision"] == "hold"
    assert result["promotion_allowed"] is False
    assert "blocked_signal_triggered" in result["failed_checks"]
    assert result["triggered_blockers"] == ["repeated_tranches_revert_to_split_required_majority"]


def test_evaluator_fail_closed_on_missing_evidence_families_and_metrics() -> None:
    criteria = _load_graduation_fixture()
    proposal = {
        "gate_id": "C",
        "from_level": 2,
        "to_level": 3,
        "gate_families_passed": [
            "evidence_grounding",
            "verification_quality",
        ],
        "evidence_signals": [
            "automation_success_across_multiple_structural_families",
        ],
        "risk_signals": [],
        "metrics": {},
        "recommendation": "promote",
    }

    result = evaluate_nat_automation_promotion(criteria, proposal)

    assert result["status"] == "rejected"
    assert result["decision"] == "hold"
    assert result["promotion_allowed"] is False
    assert "missing_required_gate_families" in result["failed_checks"]
    assert "missing_must_show_evidence" in result["failed_checks"]
    assert "missing_required_metrics" in result["failed_checks"]


def test_evaluator_rejects_unknown_gate_fail_closed() -> None:
    criteria = _load_graduation_fixture()
    proposal = {
        "gate_id": "Z",
        "from_level": 0,
        "to_level": 1,
        "gate_families_passed": criteria["gate_families_required"],
        "evidence_signals": [],
        "risk_signals": [],
        "metrics": {},
        "recommendation": "promote",
    }

    result = evaluate_nat_automation_promotion(criteria, proposal)

    assert result["status"] == "rejected"
    assert result["decision"] == "hold"
    assert result["promotion_allowed"] is False
    assert result["failed_checks"] == ["gate_not_found"]


def test_report_surface_wraps_evaluation_deterministically() -> None:
    criteria = _load_graduation_fixture()
    proposal = {
        "proposal_id": "proposal-123",
        "gate_id": "A",
        "from_level": 0,
        "to_level": 1,
        "gate_families_passed": criteria["gate_families_required"],
        "evidence_signals": [
            "reviewer_packets_for_representative_split_shapes",
            "bounded_follow_depth_present_and_fail_closed",
            "split_plan_verification_on_representative_reviewed_plans",
            "uncertainty_flags_preserved",
        ],
        "risk_signals": [],
        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
        "recommendation": "promote",
    }

    report = build_nat_automation_graduation_report(criteria, proposal)

    assert report["schema_version"] == AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION
    assert report["proposal_id"] == "proposal-123"
    assert report["gate_id"] == "A"
    assert report["status"] == "approved"
    assert report["decision"] == "promote"
    assert report["promotion_allowed"] is True
    assert report["failed_checks"] == []


def test_batch_report_surface_aggregates_mixed_outcomes_fail_closed() -> None:
    criteria = _load_graduation_fixture()
    proposal_batch = {
        "batch_id": "batch-1",
        "proposals": [
            {
                "proposal_id": "p-approve",
                "gate_id": "A",
                "from_level": 0,
                "to_level": 1,
                "gate_families_passed": criteria["gate_families_required"],
                "evidence_signals": [
                    "reviewer_packets_for_representative_split_shapes",
                    "bounded_follow_depth_present_and_fail_closed",
                    "split_plan_verification_on_representative_reviewed_plans",
                    "uncertainty_flags_preserved",
                ],
                "risk_signals": [],
                "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                "recommendation": "promote",
            },
            {
                "proposal_id": "p-reject",
                "gate_id": "B",
                "from_level": 1,
                "to_level": 2,
                "gate_families_passed": criteria["gate_families_required"],
                "evidence_signals": [
                    "repeated_family_scoped_direct_safe_behavior",
                    "stable_after_state_verification_across_repeated_tranches",
                    "false_positive_rate_within_family_budget",
                    "hold_and_abstain_paths_effective",
                ],
                "risk_signals": ["repeated_tranches_revert_to_split_required_majority"],
                "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                "recommendation": "promote",
            },
        ],
    }

    report = build_nat_automation_graduation_batch_report(criteria, proposal_batch)

    assert report["schema_version"] == AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION
    assert report["batch_id"] == "batch-1"
    assert report["proposal_count"] == 2
    assert report["summary"]["approved_count"] == 1
    assert report["summary"]["rejected_count"] == 1
    assert report["summary"]["fail_closed_count"] == 1


def test_evidence_report_surface_holds_when_repeated_runs_include_fail_closed_rows() -> None:
    criteria = _load_graduation_fixture()
    repeated_batches = {
        "evidence_batch_id": "evidence-1",
        "runs": [
            {
                "run_id": "run-1",
                "batch_id": "batch-1",
                "proposals": [
                    {
                        "proposal_id": "p-1",
                        "gate_id": "A",
                        "from_level": 0,
                        "to_level": 1,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "reviewer_packets_for_representative_split_shapes",
                            "bounded_follow_depth_present_and_fail_closed",
                            "split_plan_verification_on_representative_reviewed_plans",
                            "uncertainty_flags_preserved",
                        ],
                        "risk_signals": [],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    },
                    {
                        "proposal_id": "p-2",
                        "gate_id": "B",
                        "from_level": 1,
                        "to_level": 2,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "repeated_family_scoped_direct_safe_behavior",
                            "stable_after_state_verification_across_repeated_tranches",
                            "false_positive_rate_within_family_budget",
                            "hold_and_abstain_paths_effective",
                        ],
                        "risk_signals": ["repeated_tranches_revert_to_split_required_majority"],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    },
                ],
            },
            {
                "run_id": "run-2",
                "batch_id": "batch-2",
                "proposals": [
                    {
                        "proposal_id": "p-3",
                        "gate_id": "A",
                        "from_level": 0,
                        "to_level": 1,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "reviewer_packets_for_representative_split_shapes",
                            "bounded_follow_depth_present_and_fail_closed",
                            "split_plan_verification_on_representative_reviewed_plans",
                            "uncertainty_flags_preserved",
                        ],
                        "risk_signals": [],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    },
                    {
                        "proposal_id": "p-4",
                        "gate_id": "B",
                        "from_level": 1,
                        "to_level": 2,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "repeated_family_scoped_direct_safe_behavior",
                            "stable_after_state_verification_across_repeated_tranches",
                            "false_positive_rate_within_family_budget",
                            "hold_and_abstain_paths_effective",
                        ],
                        "risk_signals": ["repeated_tranches_revert_to_split_required_majority"],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    },
                ],
            },
        ],
    }

    report = build_nat_automation_graduation_evidence_report(criteria, repeated_batches, min_runs=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert "rejected_proposals_present" in report["readiness_failed_reasons"]
    assert "fail_closed_proposals_present" in report["readiness_failed_reasons"]
    assert "mixed_gate_scope" in report["readiness_failed_reasons"]


def test_evidence_report_surface_promotes_when_repeated_runs_are_clean_and_consistent() -> None:
    criteria = _load_graduation_fixture()
    repeated_batches = {
        "evidence_batch_id": "evidence-2",
        "runs": [
            {
                "run_id": "run-1",
                "batch_id": "batch-1",
                "proposals": [
                    {
                        "proposal_id": "p-1",
                        "gate_id": "A",
                        "from_level": 0,
                        "to_level": 1,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "reviewer_packets_for_representative_split_shapes",
                            "bounded_follow_depth_present_and_fail_closed",
                            "split_plan_verification_on_representative_reviewed_plans",
                            "uncertainty_flags_preserved",
                        ],
                        "risk_signals": [],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    }
                ],
            },
            {
                "run_id": "run-2",
                "batch_id": "batch-2",
                "proposals": [
                    {
                        "proposal_id": "p-2",
                        "gate_id": "A",
                        "from_level": 0,
                        "to_level": 1,
                        "gate_families_passed": criteria["gate_families_required"],
                        "evidence_signals": [
                            "reviewer_packets_for_representative_split_shapes",
                            "bounded_follow_depth_present_and_fail_closed",
                            "split_plan_verification_on_representative_reviewed_plans",
                            "uncertainty_flags_preserved",
                        ],
                        "risk_signals": [],
                        "metrics": {metric: {"observed": 1} for metric in criteria["metrics_required"]},
                        "recommendation": "promote",
                    }
                ],
            },
        ],
    }

    report = build_nat_automation_graduation_evidence_report(criteria, repeated_batches, min_runs=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["status"] == "ready"
    assert report["decision"] == "promote"
    assert report["promotion_ready"] is True
    assert report["readiness_failed_reasons"] == []
    assert report["readiness_scope"]["gate_consistent"] is True
    assert report["readiness_scope"]["gate_id"] == "A"


def test_evidence_report_surface_holds_gate_b_candidate_when_only_one_subset_run_exists() -> None:
    criteria = _load_graduation_fixture()
    repeated_batches = _load_nat_cohort_a_gate_b_candidate_evidence_fixture()

    report = build_nat_automation_graduation_evidence_report(criteria, repeated_batches, min_runs=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert report["readiness_failed_reasons"] == ["insufficient_repeated_runs"]
    assert report["readiness_scope"]["gate_consistent"] is True
    assert report["readiness_scope"]["gate_id"] == "B"
    assert report["summary"]["approved_count"] == 1
    assert report["summary"]["held_count"] == 0
    assert report["summary"]["rejected_count"] == 0
    assert report["summary"]["fail_closed_count"] == 0


def test_evidence_report_surface_promotes_gate_b_candidate_when_two_clean_subset_runs_exist() -> None:
    criteria = _load_graduation_fixture()
    repeated_batches = _load_nat_cohort_a_gate_b_candidate_evidence_ready_fixture()

    report = build_nat_automation_graduation_evidence_report(criteria, repeated_batches, min_runs=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["status"] == "ready"
    assert report["decision"] == "promote"
    assert report["promotion_ready"] is True
    assert report["readiness_failed_reasons"] == []
    assert report["readiness_scope"]["gate_consistent"] is True
    assert report["readiness_scope"]["gate_id"] == "B"
    assert report["readiness_scope"]["run_count"] == 2
    assert report["summary"]["approved_count"] == 2
    assert report["summary"]["held_count"] == 0
    assert report["summary"]["rejected_count"] == 0


def test_build_gate_b_proposal_batches_from_single_verification_run_holds_on_repetition_gap() -> None:
    criteria = _load_graduation_fixture()
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_run_fixture()

    proposal_batches = build_nat_gate_b_proposal_batches_from_verification_runs(verification_runs)
    report = build_nat_automation_graduation_evidence_report(criteria, proposal_batches)

    assert proposal_batches["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert len(proposal_batches["runs"]) == 1
    proposal = proposal_batches["runs"][0]["proposals"][0]
    assert proposal["metrics"]["after_state_verification_pass_rate"]["observed"] == 1.0
    assert proposal["metrics"]["false_positive_rate_and_severity"]["observed"] == 0.0
    assert proposal["verification_report"]["summary"]["verified_candidate_count"] == 2
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert report["readiness_failed_reasons"] == ["insufficient_repeated_runs"]


def test_build_gate_b_proposal_batches_from_repeated_verification_runs_produces_ready_report() -> None:
    criteria = _load_graduation_fixture()
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()

    proposal_batches = build_nat_gate_b_proposal_batches_from_verification_runs(verification_runs)
    report = build_nat_automation_graduation_evidence_report(criteria, proposal_batches)

    assert proposal_batches["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert len(proposal_batches["runs"]) == 2
    assert proposal_batches["promotion_scope"]["scope_status"] == "pilot_ready_only"
    assert proposal_batches["promotion_scope"]["generalization_allowed"] is False
    assert proposal_batches["promotion_scope"]["candidate_ids"] == [
        "Q1068745|P5991|1",
        "Q1489170|P5991|1",
    ]
    for run in proposal_batches["runs"]:
        proposal = run["proposals"][0]
        assert proposal["gate_id"] == "B"
        assert proposal["recommendation"] == "promote"
        assert proposal["promotion_scope"]["scope_status"] == "pilot_ready_only"
        assert proposal["promotion_scope"]["generalization_requires_new_evidence"] is True
        assert proposal["risk_signals"] == []
        assert proposal["metrics"]["direct_safe_yield_by_family"]["observed"] == 1.0
        assert proposal["metrics"]["after_state_verification_pass_rate"]["observed"] == 1.0
        assert proposal["metrics"]["false_positive_rate_and_severity"]["observed"] == 0.0
        assert proposal["verification_report"]["summary"]["counts_by_status"] == {"verified": 2}
    assert report["status"] == "ready"
    assert report["decision"] == "promote"
    assert report["promotion_ready"] is True
    assert report["readiness_failed_reasons"] == []
    assert report["summary"]["fail_closed_count"] == 0
    assert report["promotion_scope"]["scope_status"] == "pilot_ready_only"
    assert report["promotion_scope"]["candidate_ids"] == [
        "Q1068745|P5991|1",
        "Q1489170|P5991|1",
    ]
    assert "does not establish readiness for the broader cohort" in report["promotion_scope"]["promotion_statement"]


def test_climate_family_seed_fixture_stays_distinct_and_fail_closed() -> None:
    seed = _load_nat_climate_family_seed_fixture()

    assert seed["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert seed["cohort_id"] == "climate_family_safe_reference_transfer"
    assert seed["checked_safe_subset"] == ["Q10651551|P5991|1"]
    assert seed["counts_by_bucket"] == {
        "safe_with_reference_transfer": 1,
        "split_required": 56,
    }
    assert seed["unresolved_pressure_status"] == "hold"
    assert seed["follow_obligation"]["trigger"] == "climate_family_safe_reference_transfer_subset"
    assert seed["replay_path"].endswith("p5991_p14143_climate_pilot_20260328")
    assert [row["candidate_id"] for row in seed["pressure_candidates"]] == [
        "Q10403939|P5991|1",
        "Q10403939|P5991|2",
        "Q10422059|P5991|1",
    ]
    assert all(row["classification"] == "split_required" for row in seed["pressure_candidates"])


def test_climate_family_single_verification_run_materializes_distinct_hold_path() -> None:
    criteria = _load_graduation_fixture()
    verification_runs = _load_nat_climate_family_verification_run_fixture()

    proposal_batches = build_nat_gate_b_proposal_batches_from_verification_runs(verification_runs)
    report = build_nat_automation_graduation_evidence_report(criteria, proposal_batches)

    assert proposal_batches["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert proposal_batches["cohort_id"] == "climate_family_safe_reference_transfer"
    assert proposal_batches["promotion_scope"]["scope_status"] == "pilot_ready_only"
    assert proposal_batches["promotion_scope"]["candidate_ids"] == ["Q10651551|P5991|1"]
    assert len(proposal_batches["runs"]) == 1
    proposal = proposal_batches["runs"][0]["proposals"][0]
    assert proposal["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert proposal["cohort_id"] == "climate_family_safe_reference_transfer"
    assert proposal["metrics"]["direct_safe_yield_by_family"]["observed"] == 1.0
    assert proposal["metrics"]["after_state_verification_pass_rate"]["observed"] == 1.0
    assert proposal["verification_report"]["summary"]["counts_by_status"] == {"verified": 1}
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert report["readiness_failed_reasons"] == ["insufficient_repeated_runs"]
    assert report["promotion_scope"]["candidate_ids"] == ["Q10651551|P5991|1"]


def test_claim_convergence_report_promotes_first_family_from_independent_runs() -> None:
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()

    report = build_nat_claim_convergence_report(verification_runs)

    assert report["schema_version"] == AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION
    assert report["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert report["summary"]["total_claims"] == 2
    assert report["summary"]["promoted_count"] == 2
    assert report["summary"]["single_run_count"] == 0
    assert report["summary"]["avg_evidence_paths_per_claim"] == 2.0
    assert report["summary"]["avg_independent_paths_per_claim"] == 2.0
    for claim in report["claims"]:
        assert claim["status"] == "PROMOTED"
        assert claim["independent_count"] == 2
        assert len(claim["evidence_paths"]) == 2
        assert len(claim["independent_root_artifact_ids"]) == 2


def test_claim_convergence_report_holds_climate_seed_as_single_run() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    expected = _load_nat_climate_family_claim_convergence_fixture()

    report = build_nat_claim_convergence_report(verification_runs)

    assert report == expected
    assert report["schema_version"] == AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION
    assert report["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert report["summary"]["total_claims"] == 1
    assert report["summary"]["single_run_count"] == 1
    assert report["summary"]["promoted_count"] == 0
    claim = report["claims"][0]
    assert claim["candidate_id"] == "Q10651551|P5991|1"
    assert claim["status"] == "SINGLE_RUN"
    assert claim["independent_count"] == 1
    assert len(claim["independent_root_artifact_ids"]) == 1


def test_confirmation_follow_queue_targets_only_single_run_claims() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    expected = _load_nat_climate_family_confirmation_queue_fixture()

    queue = build_nat_confirmation_follow_queue(verification_runs)

    assert queue == expected
    assert queue["schema_version"] == AUTOMATION_GRADUATION_CONFIRMATION_QUEUE_SCHEMA_VERSION
    assert queue["summary"]["claim_count"] == 1
    assert queue["summary"]["single_run_queue_count"] == 1
    row = queue["queue_rows"][0]
    assert row["claim_id"] == "Q10651551|P5991|1"
    assert row["blocking_reason"] == "insufficient_independent_evidence"
    assert row["follow_goal"] == "find_independent_confirmation"
    assert row["missing_independent_count"] == 1


def test_confirmation_intake_contract_targets_only_single_run_claims() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    expected = _load_nat_climate_family_confirmation_intake_contract_fixture()

    contract = build_nat_confirmation_intake_contract(verification_runs)

    assert contract == expected
    assert contract["schema_version"] == AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION
    assert contract["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert contract["summary"]["claim_count"] == 1
    assert contract["summary"]["intake_request_count"] == 1
    row = contract["intake_rows"][0]
    assert row["claim_id"] == "Q10651551|P5991|1"
    assert row["candidate_id"] == "Q10651551|P5991|1"
    assert row["status"] == "awaiting_independent_evidence"
    assert row["missing_independent_count"] == 1
    assert row["required_artifact_contract"]["must_supply"] == ["migration_pack", "after_payload"]
    assert row["required_artifact_contract"]["must_include_new_window_id"] is True
    assert row["required_artifact_contract"]["must_be_revision_locked"] is True
    assert row["required_artifact_contract"]["must_be_independent_of_root_artifact_ids"]
    assert row["runtime_reuse_contract"]["entrypoint"] == "verifier_to_convergence_chain"
    assert row["runtime_reuse_contract"]["steps"] == [
        "verify_migration_pack_against_after_state",
        "build_nat_claim_convergence_report",
        "build_nat_confirmation_follow_queue",
    ]


def test_confirmation_intake_contract_is_empty_for_promoted_family() -> None:
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()

    contract = build_nat_confirmation_intake_contract(verification_runs)

    assert contract["schema_version"] == AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION
    assert contract["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert contract["summary"]["claim_count"] == 2
    assert contract["summary"]["intake_request_count"] == 0
    assert contract["intake_rows"] == []


def test_confirmation_intake_report_aggregates_held_and_promoted_families() -> None:
    report = build_nat_confirmation_intake_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
        ]
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_REPORT_SCHEMA_VERSION
    assert report["summary"]["family_count"] == 2
    assert report["summary"]["families_with_requests"] == 1
    assert report["summary"]["intake_request_count"] == 1
    assert len(report["contracts"]) == 2
    row = report["intake_rows"][0]
    assert row["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert row["candidate_id"] == "Q10651551|P5991|1"
    assert row["missing_independent_count"] == 1


def test_claim_convergence_does_not_count_duplicated_artifact_twice() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    duplicated_runs = {
        **verification_runs,
        "runs": [
            verification_runs["runs"][0],
            {
                **verification_runs["runs"][0],
                "run_id": "run-2026-04-03-climate-duplicate",
            },
        ],
    }

    report = build_nat_claim_convergence_report(duplicated_runs)

    assert report["summary"]["total_claims"] == 1
    assert report["summary"]["single_run_count"] == 1
    claim = report["claims"][0]
    assert claim["status"] == "SINGLE_RUN"
    assert claim["evidence_count"] == 2
    assert claim["independent_count"] == 1


def test_claim_convergence_does_not_count_bridge_derived_artifact_as_independent() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    first_report = build_nat_claim_convergence_report(verification_runs)
    original_root = first_report["claims"][0]["independent_root_artifact_ids"][0]
    bridge_derived_runs = {
        **verification_runs,
        "runs": [
            verification_runs["runs"][0],
            {
                **verification_runs["runs"][0],
                "run_id": "run-2026-04-03-climate-bridge-derived",
                "derived_from_root_artifact_ids": [original_root],
            },
        ],
    }

    report = build_nat_claim_convergence_report(bridge_derived_runs)

    assert report["summary"]["total_claims"] == 1
    assert report["summary"]["single_run_count"] == 1
    claim = report["claims"][0]
    assert claim["status"] == "SINGLE_RUN"
    assert claim["evidence_count"] == 2
    assert claim["independent_count"] == 1
    assert claim["independent_root_artifact_ids"] == [original_root]


def test_governance_index_holds_when_any_snapshot_not_ready() -> None:
    criteria = _load_graduation_fixture()
    snapshots = {
        "governance_batch_id": "gov-1",
        "snapshots": [
            {
                "snapshot_id": "s1",
                "evidence_report": {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "readiness_failed_reasons": [],
                    "readiness_scope": {"gate_id": "A", "run_count": 2},
                    "summary": {
                        "approved_count": 2,
                        "held_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
            {
                "snapshot_id": "s2",
                "evidence_report": {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "readiness_failed_reasons": ["rejected_proposals_present"],
                    "readiness_scope": {"gate_id": "A", "run_count": 2},
                    "summary": {
                        "approved_count": 1,
                        "held_count": 0,
                        "rejected_count": 1,
                        "fail_closed_count": 1,
                    },
                },
            },
        ],
    }

    report = build_nat_automation_graduation_governance_index(criteria, snapshots, min_snapshots=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert "not_ready_snapshots_present" in report["readiness_failed_reasons"]
    assert "rejected_proposals_present" in report["readiness_failed_reasons"]
    assert "fail_closed_proposals_present" in report["readiness_failed_reasons"]


def test_governance_index_promotes_when_all_snapshots_ready_and_consistent() -> None:
    criteria = _load_graduation_fixture()
    snapshots = {
        "governance_batch_id": "gov-2",
        "snapshots": [
            {
                "snapshot_id": "s1",
                "evidence_report": {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "readiness_failed_reasons": [],
                    "readiness_scope": {"gate_id": "A", "run_count": 2},
                    "summary": {
                        "approved_count": 2,
                        "held_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
            {
                "snapshot_id": "s2",
                "evidence_report": {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "readiness_failed_reasons": [],
                    "readiness_scope": {"gate_id": "A", "run_count": 2},
                    "summary": {
                        "approved_count": 1,
                        "held_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
        ],
    }

    report = build_nat_automation_graduation_governance_index(criteria, snapshots, min_snapshots=2)

    assert report["schema_version"] == AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION
    assert report["status"] == "ready"
    assert report["decision"] == "promote"
    assert report["promotion_ready"] is True
    assert report["readiness_failed_reasons"] == []
    assert report["scope"]["gate_scope_consistent"] is True
    assert report["scope"]["gate_id"] == "A"


def test_governance_summary_holds_when_any_governance_index_not_ready() -> None:
    criteria = _load_graduation_fixture()
    governance_snapshots = {
        "governance_summary_id": "gov-summary-1",
        "snapshots": [
            {
                "snapshot_id": "g1",
                "governance_index": {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "scope": {"gate_id": "A", "snapshot_count": 2},
                    "summary": {
                        "ready_count": 2,
                        "not_ready_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
            {
                "snapshot_id": "g2",
                "governance_index": {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "scope": {"gate_id": "A", "snapshot_count": 2},
                    "summary": {
                        "ready_count": 1,
                        "not_ready_count": 1,
                        "rejected_count": 1,
                        "fail_closed_count": 1,
                    },
                },
            },
        ],
    }

    report = build_nat_automation_graduation_governance_summary(
        criteria,
        governance_snapshots,
        min_indexes=2,
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION
    assert report["status"] == "not_ready"
    assert report["decision"] == "hold"
    assert report["promotion_ready"] is False
    assert "not_ready_governance_indexes_present" in report["readiness_failed_reasons"]
    assert "rejected_proposals_present" in report["readiness_failed_reasons"]
    assert "fail_closed_proposals_present" in report["readiness_failed_reasons"]


def test_governance_summary_promotes_when_governance_indexes_are_ready_and_consistent() -> None:
    criteria = _load_graduation_fixture()
    governance_snapshots = {
        "governance_summary_id": "gov-summary-2",
        "snapshots": [
            {
                "snapshot_id": "g1",
                "governance_index": {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "scope": {"gate_id": "A", "snapshot_count": 2},
                    "summary": {
                        "ready_count": 2,
                        "not_ready_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
            {
                "snapshot_id": "g2",
                "governance_index": {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "ready",
                    "decision": "promote",
                    "promotion_ready": True,
                    "scope": {"gate_id": "A", "snapshot_count": 2},
                    "summary": {
                        "ready_count": 2,
                        "not_ready_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                },
            },
        ],
    }

    report = build_nat_automation_graduation_governance_summary(
        criteria,
        governance_snapshots,
        min_indexes=2,
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION
    assert report["status"] == "ready"
    assert report["decision"] == "promote"
    assert report["promotion_ready"] is True
    assert report["readiness_failed_reasons"] == []
    assert report["scope"]["gate_scope_consistent"] is True
    assert report["scope"]["gate_id"] == "A"
