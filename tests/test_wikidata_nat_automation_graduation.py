from __future__ import annotations

import copy
import json
from pathlib import Path

from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION
from src.models.conflict import CONFLICT_SCHEMA_VERSION
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION
from src.models.temporal import TEMPORAL_SCHEMA_VERSION
from src.metrics.nat_cross_lane_metrics import collect_nat_cross_lane_metrics, NatCrossLaneMetrics
from src.ontology.wikidata_nat_automation_graduation import (
    AUTOMATION_GRADUATION_CLIMATE_CROSS_ROW_ACQUISITION_PLAN_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CLIMATE_FAMILY_V2_SEED_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_BATCH_FINDER_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_BATCH_EXPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_BACKEND_PLAN_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_CANDIDATE_CONTRACT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_EXECUTED_ROWS_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PROOF_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_LIFECYCLE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_POST_WRITE_CONTRACT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_RECEIPT_CONTRACT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_MIGRATION_SIMULATION_CONTRACT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_P5991_SEMANTIC_FAMILY_SELECTOR_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_P5991_SEMANTIC_TRIAGE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_INTAKE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_ACQUISITION_TASK_QUEUE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_CONFIRMATION_QUEUE_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_FAMILY_ACQUISITION_PLAN_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_STATE_MACHINE_REPORT_SCHEMA_VERSION,
    AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
    build_nat_acquisition_task_queue,
    build_nat_claim_convergence_report,
    build_nat_automation_graduation_batch_report,
    build_nat_automation_graduation_evidence_report,
    build_nat_automation_graduation_governance_index,
    build_nat_automation_graduation_governance_summary,
    build_nat_automation_graduation_report,
    build_nat_climate_claim_signature,
    build_nat_climate_cross_row_acquisition_plan,
    build_nat_climate_family_v2_seed,
    build_nat_broader_batch_selector,
    build_nat_p5991_semantic_family_selector,
    build_nat_p5991_semantic_triage_report,
    build_nat_migration_batch_finder_report,
    build_nat_migration_batch_export,
    build_nat_migration_backend_plan,
    build_nat_migration_candidate_contracts,
    build_nat_migration_executed_rows,
    build_nat_migration_execution_payload,
    build_nat_migration_execution_proof,
    build_nat_migration_lifecycle_report,
    build_nat_migration_simulation_contract,
    build_nat_confirmation_intake_contract,
    build_nat_confirmation_intake_report,
    build_nat_confirmation_follow_queue,
    build_nat_family_acquisition_plan,
    build_nat_gate_b_proposal_batches_from_verification_runs,
    build_nat_same_family_after_state_verification_run_from_entity_export,
    merge_nat_acquired_evidence,
    run_nat_acquisition_tasks,
    run_nat_live_same_family_acquisition_sweep,
    run_nat_same_family_after_state_acquisition_tasks,
    verify_nat_climate_cross_source_confirmation,
    build_nat_state_machine_report,
    evaluate_nat_automation_promotion,
    build_nat_post_write_verification_report,
    build_nat_sandbox_post_write_verification_report,
    build_nat_post_write_contract,
    build_nat_execution_receipt_contract,
    classify_nat_p5991_semantic_bucket,
    AUTOMATION_GRADUATION_POST_WRITE_VERIFICATION_SCHEMA_VERSION,
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


def _load_nat_verification_runs_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
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


def _load_nat_climate_family_manual_acquired_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_manual_acquired_verification_run_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_manual_acquired_entity_export_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_manual_acquired_entity_export_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_family_v2_seed_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_family_v2_seed_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_cross_row_acquisition_plan_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_cross_row_acquisition_plan_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_climate_cross_row_confirmation_source_unit_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_climate_cross_row_confirmation_source_unit_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_current_climate_entity_export_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data"
            / "ontology"
            / "wikidata_migration_packs"
            / "p5991_p14143_climate_pilot_20260328"
            / "entity_exports"
            / "q10651551_t2_2435181075.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_family_seed_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_family_seed_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_family_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_family_verification_run_20260403.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_family_acquisition_plan_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_family_acquisition_plan_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_family_manual_acquired_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_family_manual_acquired_verification_run_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_family_manual_acquired_remaining_verification_run_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_family_manual_acquired_remaining_verification_run_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_live_q16572_entity_export_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_live_q16572_entity_export_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_parthood_live_acquisition_scan_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_parthood_live_acquisition_scan_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_business_family_migration_batch_export_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_business_family_migration_batch_export_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_business_family_migration_executed_rows_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_business_family_migration_executed_rows_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _load_nat_business_family_migration_execution_proof_fixture() -> dict:
    return json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "wikidata"
            / "wikidata_nat_business_family_migration_execution_proof_20260404.json"
        ).read_text(encoding="utf-8")
    )


def _encode_test_datavalue(value: str) -> dict:
    if value.startswith("Q") and value[1:].isdigit():
        return {
            "value": {
                "entity-type": "item",
                "numeric-id": int(value[1:]),
                "id": value,
            },
            "type": "wikibase-entityid",
        }
    if value.startswith("+") and "T" in value:
        return {
            "value": {
                "time": value,
                "timezone": 0,
                "before": 0,
                "after": 0,
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
            "type": "time",
        }
    return {"value": value, "type": "string"}


def _statement_from_claim_bundle(bundle: dict, *, suffix: str) -> dict:
    qualifiers = {}
    for property_id, values in bundle.get("qualifiers", {}).items():
        qualifiers[property_id] = [
            {
                "snaktype": "value",
                "property": property_id,
                "datavalue": _encode_test_datavalue(str(value)),
            }
            for value in values
        ]

    references = []
    for reference_index, reference in enumerate(bundle.get("references", []), start=1):
        snaks = {}
        for property_id, values in reference.items():
            snaks[property_id] = [
                {
                    "snaktype": "value",
                    "property": property_id,
                    "datavalue": _encode_test_datavalue(str(value)),
                }
                for value in values
            ]
        references.append(
            {
                "hash": f"ref-{suffix}-{reference_index}",
                "snaks": snaks,
                "snaks-order": sorted(snaks),
            }
        )

    statement = {
        "mainsnak": {
            "snaktype": "value",
            "property": bundle["property"],
            "datavalue": _encode_test_datavalue(str(bundle["value"])),
        },
        "type": "statement",
        "id": f"{bundle['subject']}${suffix}",
        "rank": bundle.get("rank", "normal"),
    }
    if qualifiers:
        statement["qualifiers"] = qualifiers
    if references:
        statement["references"] = references
    return statement


def _entity_export_from_candidate(candidate: dict, *, revision_id: int) -> dict:
    entity_qid = candidate["entity_qid"]
    claims = {}
    for index, key in enumerate(["claim_bundle_before", "claim_bundle_after"], start=1):
        bundle = candidate.get(key)
        if not isinstance(bundle, dict):
            continue
        property_id = bundle["property"]
        claims.setdefault(property_id, []).append(
            _statement_from_claim_bundle(bundle, suffix=f"{revision_id}-{index}")
        )
    return {
        "_source_revision": revision_id,
        "entities": {
            entity_qid: {
                "id": entity_qid,
                "lastrevid": revision_id,
                "claims": claims,
            }
        },
    }


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
    assert report["claim_schema_version"] == NAT_CLAIM_SCHEMA_VERSION
    assert report["convergence_schema_version"] == CONVERGENCE_SCHEMA_VERSION
    assert report["temporal_schema_version"] == TEMPORAL_SCHEMA_VERSION
    assert report["conflict_schema_version"] == CONFLICT_SCHEMA_VERSION
    assert report["action_policy_schema_version"] == ACTION_POLICY_SCHEMA_VERSION
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
        assert claim["nat_claim"]["schema_version"] == NAT_CLAIM_SCHEMA_VERSION
        assert claim["nat_claim"]["claim_id"] == claim["claim_id"]
        assert claim["nat_claim"]["candidate_id"] == claim["candidate_id"]
        assert claim["nat_claim"]["canonical_form"] == claim["canonical_form"]
        assert claim["convergence"]["schema_version"] == CONVERGENCE_SCHEMA_VERSION
        assert claim["convergence"]["claim_id"] == claim["claim_id"]
        assert claim["convergence"]["convergence_state"] == "GOVERNED"
        assert claim["convergence"]["merged_evidence_basis"]["source_count"] == 2
        assert claim["temporal"]["schema_version"] == TEMPORAL_SCHEMA_VERSION
        assert claim["temporal"]["claim_id"] == claim["claim_id"]
        assert claim["temporal"]["valid_from"] == "2026-04-03"
        assert claim["temporal"]["observed_at"] == "2026-04-03"
        assert claim["temporal"]["revision_basis"]["observation_count"] == 2
        assert claim["conflict_set"]["schema_version"] == CONFLICT_SCHEMA_VERSION
        assert claim["conflict_set"]["claim_id"] == claim["claim_id"]
        assert claim["conflict_set"]["conflict_type"] == "none"
        assert claim["conflict_set"]["resolution_status"] == "clear"
        assert claim["action_policy"]["schema_version"] == ACTION_POLICY_SCHEMA_VERSION
        assert claim["action_policy"]["claim_id"] == claim["claim_id"]
        assert claim["action_policy"]["actionability"] == "can_act"


def test_claim_convergence_report_holds_climate_seed_as_single_run() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    expected = _load_nat_climate_family_claim_convergence_fixture()

    report = build_nat_claim_convergence_report(verification_runs)

    assert report == expected
    assert report["schema_version"] == AUTOMATION_GRADUATION_CLAIM_CONVERGENCE_SCHEMA_VERSION
    assert report["temporal_schema_version"] == TEMPORAL_SCHEMA_VERSION
    assert report["conflict_schema_version"] == CONFLICT_SCHEMA_VERSION
    assert report["action_policy_schema_version"] == ACTION_POLICY_SCHEMA_VERSION
    assert report["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert report["summary"]["total_claims"] == 1
    assert report["summary"]["single_run_count"] == 1
    assert report["summary"]["promoted_count"] == 0
    claim = report["claims"][0]
    assert claim["candidate_id"] == "Q10651551|P5991|1"
    assert claim["status"] == "SINGLE_RUN"
    assert claim["independent_count"] == 1
    assert len(claim["independent_root_artifact_ids"]) == 1
    assert claim["temporal"]["schema_version"] == TEMPORAL_SCHEMA_VERSION
    assert claim["temporal"]["observed_at"] == "2026-04-03"
    assert claim["conflict_set"]["schema_version"] == CONFLICT_SCHEMA_VERSION
    assert claim["conflict_set"]["conflict_type"] == "none"
    assert claim["action_policy"]["schema_version"] == ACTION_POLICY_SCHEMA_VERSION
    assert claim["action_policy"]["actionability"] == "must_abstain"


def test_claim_convergence_report_emits_conflict_set_for_divergent_canonical_forms() -> None:
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    divergent_runs = copy.deepcopy(verification_runs)
    second_run = divergent_runs["runs"][1]
    second_candidate = second_run["migration_pack"]["candidates"][0]
    second_candidate["claim_bundle_after"]["value"] = "+999999"
    for bundle in second_run["after_payload"]["windows"][0]["statement_bundles"]:
        if bundle["subject"] == "Q1068745" and bundle["property"] == "P14143":
            bundle["value"] = "+999999"

    report = build_nat_claim_convergence_report(divergent_runs)

    conflicted_claim = next(
        claim for claim in report["claims"] if claim["claim_id"] == "Q1068745|P5991|1"
    )
    assert conflicted_claim["conflict_set"]["schema_version"] == CONFLICT_SCHEMA_VERSION
    assert conflicted_claim["conflict_set"]["conflict_type"] == "canonical_form_divergence"
    assert conflicted_claim["conflict_set"]["resolution_status"] == "requires_review"
    assert conflicted_claim["conflict_set"]["review_queue_ref"] == "review:Q1068745|P5991|1"
    assert len(conflicted_claim["conflict_set"]["evidence_rows"]) == 2
    assert conflicted_claim["action_policy"]["actionability"] == "must_review"


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
    assert row["suggested_evidence_routes"] == [
        {
            "priority": 1,
            "route_id": "Q10651551|P5991|1:same_family_after_state",
            "route_kind": "same_family_after_state",
            "source_family": "wikidata_migration_pack",
            "why": "A new revision-locked after-state bundle for the same family is the shortest truthful path to independent confirmation.",
        },
        {
            "priority": 2,
            "route_id": "Q10651551|P5991|1:cross_row_migrated_p14143",
            "route_kind": "cross_row_migrated_p14143",
            "source_family": "wikidata_sparql_p14143",
            "why": "Climate-family rows can recover through already-migrated P14143 rows that match the same normalized climate claim shape.",
        },
        {
            "priority": 3,
            "route_id": "Q10651551|P5991|1:phi_text_bridge",
            "route_kind": "text_bridge_promoted_observation",
            "source_family": "wikidata_phi_text_bridge",
            "why": "The bounded Phi text bridge is the repo-approved additive pressure lane for climate-family evidence, but it cannot replace structured verification by itself.",
        },
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


def test_acquisition_task_queue_expands_suggested_routes_for_held_claims() -> None:
    queue = build_nat_acquisition_task_queue(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
        ]
    )

    assert queue["schema_version"] == AUTOMATION_GRADUATION_ACQUISITION_TASK_QUEUE_SCHEMA_VERSION
    assert queue["summary"]["task_count"] == 3
    assert queue["summary"]["family_count"] == 2
    assert queue["summary"]["families_with_requests"] == 1
    assert [task["route_kind"] for task in queue["tasks"]] == [
        "same_family_after_state",
        "cross_row_migrated_p14143",
        "text_bridge_promoted_observation",
    ]
    assert all(task["status"] == "PENDING" for task in queue["tasks"])
    assert all(task["claim_id"] == "Q10651551|P5991|1" for task in queue["tasks"])


def test_state_machine_report_tracks_promoted_and_awaiting_evidence_families() -> None:
    report = build_nat_state_machine_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
        ]
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_STATE_MACHINE_REPORT_SCHEMA_VERSION
    assert report["summary"]["family_count"] == 2
    assert report["summary"]["promoted_family_count"] == 1
    assert report["summary"]["awaiting_evidence_family_count"] == 0
    assert report["summary"]["migration_pending_family_count"] == 1
    assert report["summary"]["ready_to_rerun_family_count"] == 0
    assert report["summary"]["promoted_family_count_by_basis"] == {"baseline_runtime": 1}
    rows = {row["family_id"]: row for row in report["families"]}
    assert rows["business_family_reconciled_low_qualifier_checked_safe_subset"]["state"] == "PROMOTED"
    assert rows["business_family_reconciled_low_qualifier_checked_safe_subset"]["state_basis"] == "baseline_runtime"
    assert rows["climate_family_safe_reference_transfer_subset"]["state"] == "MIGRATION_PENDING"
    assert rows["climate_family_safe_reference_transfer_subset"]["state_basis"] == "baseline_runtime"
    assert rows["climate_family_safe_reference_transfer_subset"]["migration_signal"] is True


def test_state_machine_report_marks_family_ready_to_rerun_after_successful_acquisition() -> None:
    report = build_nat_state_machine_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
        ],
        acquisition_events=[
            {
                "claim_id": "Q10651551|P5991|1",
                "status": "SUCCESS",
                "route_id": "Q10651551|P5991|1:same_family_after_state",
                "family_id": "climate_family_safe_reference_transfer_subset",
                "evidence_provenance_kind": "live_same_family_acquisition",
            }
        ],
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_STATE_MACHINE_REPORT_SCHEMA_VERSION
    assert report["summary"]["promoted_family_count"] == 1
    assert report["summary"]["awaiting_evidence_family_count"] == 0
    assert report["summary"]["migration_pending_family_count"] == 0
    assert report["summary"]["ready_to_rerun_family_count"] == 1
    assert report["summary"]["ready_to_rerun_family_count_by_basis"] == {
        "live_same_family_acquisition": 1
    }
    rows = {row["family_id"]: row for row in report["families"]}
    assert rows["business_family_reconciled_low_qualifier_checked_safe_subset"]["state"] == "PROMOTED"
    assert rows["climate_family_safe_reference_transfer_subset"]["state"] == "READY_TO_RERUN"
    assert rows["climate_family_safe_reference_transfer_subset"]["state_basis"] == "live_same_family_acquisition"


def test_climate_claim_signature_normalizes_row_local_claim_shape() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    canonical_form = verification_runs["runs"][0]["migration_pack"]["candidates"][0]["claim_bundle_after"]

    signature = build_nat_climate_claim_signature(canonical_form)

    assert signature == {
        "subject": "Q10651551",
        "subject_class": "enterprise",
        "metric_kind": "annual_greenhouse_gas_emissions",
        "property_family": "annual_greenhouse_gas_emissions",
        "normalized_value": "442",
        "year": "2021",
        "unit": "co2e",
        "determination_method": [],
        "role_scope": [],
        "applies_to_part": [],
    }


def test_climate_family_v2_seed_materializes_live_p14143_candidates() -> None:
    candidates = _load_nat_climate_family_v2_seed_fixture()["candidate_rows"]

    seed = build_nat_climate_family_v2_seed(candidates)

    assert seed == _load_nat_climate_family_v2_seed_fixture()
    assert seed["schema_version"] == AUTOMATION_GRADUATION_CLIMATE_FAMILY_V2_SEED_SCHEMA_VERSION
    assert seed["family_id"] == "climate_family_v2_live_p14143_subset"
    assert seed["summary"]["candidate_count"] == 3


def test_climate_cross_row_acquisition_plan_targets_live_p14143_candidates() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    climate_v2_seed = _load_nat_climate_family_v2_seed_fixture()

    plan = build_nat_climate_cross_row_acquisition_plan(verification_runs, climate_v2_seed)

    assert plan == _load_nat_climate_cross_row_acquisition_plan_fixture()
    assert plan["schema_version"] == AUTOMATION_GRADUATION_CLIMATE_CROSS_ROW_ACQUISITION_PLAN_SCHEMA_VERSION
    assert plan["summary"]["candidate_count"] == 3
    assert plan["summary"]["supports_claim_id"] == "Q10651551|P5991|1"


def test_climate_cross_row_confirmation_accepts_independent_migrated_p14143_row() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    original_claim = verification_runs["runs"][0]["migration_pack"]["candidates"][0]["claim_bundle_after"]
    migrated_source_unit = _load_nat_climate_cross_row_confirmation_source_unit_fixture()

    confirmation = verify_nat_climate_cross_source_confirmation(
        original_claim,
        migrated_source_unit,
    )

    assert confirmation["confirmed"] is True
    assert confirmation["failed_checks"] == []
    assert confirmation["evidence_provenance_kind"] == "cross_row_migrated_p14143"
    assert confirmation["candidate_signature"]["year"] == "2021"
    assert confirmation["candidate_signature"]["normalized_value"] == "442"


def test_same_family_after_state_verification_run_builder_parses_entity_export() -> None:
    verification_runs = _load_nat_climate_family_verification_run_fixture()
    entity_export_payload = _load_nat_climate_family_manual_acquired_entity_export_fixture()

    verification_run = build_nat_same_family_after_state_verification_run_from_entity_export(
        verification_runs,
        candidate_id="Q10651551|P5991|1",
        entity_export_payload=entity_export_payload,
        run_id="run-2026-04-03-climate-entity-export",
        batch_id="nat-climate-entity-export-batch",
    )

    run = verification_run["runs"][0]
    assert verification_run["family_id"] == "climate_family_safe_reference_transfer_subset"
    assert verification_run["candidate_ids"] == ["Q10651551|P5991|1"]
    assert run["evidence_provenance_kind"] == "live_same_family_acquisition"
    assert run["root_artifact_id"] == "wikidata_entity_export:Q10651551:manual-2435181076"
    bundles = run["after_payload"]["windows"][0]["statement_bundles"]
    assert {bundle["property"] for bundle in bundles} == {"P5991", "P14143"}


def test_same_family_after_state_acquisition_fails_on_current_climate_entity_export() -> None:
    verification_batches = [_load_nat_climate_family_verification_run_fixture()]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    same_family_task = next(task for task in task_queue["tasks"] if task["route_kind"] == "same_family_after_state")

    event_report = run_nat_same_family_after_state_acquisition_tasks(
        task_queue,
        verification_batches,
        [
            {
                "task_id": same_family_task["task_id"],
                "entity_export_payload": _load_nat_current_climate_entity_export_fixture(),
                "run_id": "run-2026-04-03-climate-live-same-root",
                "batch_id": "nat-climate-live-batch",
            }
        ],
    )

    assert event_report["schema_version"] == AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION
    assert event_report["summary"]["success_count"] == 0
    failure = next(event for event in event_report["events"] if event["route_id"] == same_family_task["route_id"])
    assert failure["failure_reason"] == "verification_target_missing"


def test_same_family_after_state_acquisition_accepts_manual_entity_export_and_promotes_climate() -> None:
    verification_batches = [_load_nat_climate_family_verification_run_fixture()]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    same_family_task = next(task for task in task_queue["tasks"] if task["route_kind"] == "same_family_after_state")

    event_report = run_nat_same_family_after_state_acquisition_tasks(
        task_queue,
        verification_batches,
        [
            {
                "task_id": same_family_task["task_id"],
                "entity_export_payload": _load_nat_climate_family_manual_acquired_entity_export_fixture(),
                "run_id": "run-2026-04-03-climate-entity-export-b",
                "batch_id": "nat-climate-entity-export-batch",
            }
        ],
    )

    assert event_report["summary"]["success_count"] == 1
    success_event = next(event for event in event_report["events"] if event["status"] == "SUCCESS")
    assert success_event["claim_id"] == "Q10651551|P5991|1"
    assert success_event["evidence_provenance_kind"] == "live_same_family_acquisition"
    assert success_event["verification_summary"]["counts_by_status"] == {"verified": 1}

    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    climate_report = build_nat_claim_convergence_report(merged_batches[0])
    assert climate_report["summary"]["promoted_count"] == 1
    assert climate_report["claims"][0]["status"] == "PROMOTED"


def test_acquisition_runner_accepts_manual_independent_artifact_and_enables_rerun() -> None:
    verification_batches = [
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
        _load_nat_climate_family_verification_run_fixture(),
    ]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    climate_task = task_queue["tasks"][0]
    manual_run = _load_nat_climate_family_manual_acquired_verification_run_fixture()

    event_report = run_nat_acquisition_tasks(
        task_queue,
        [
            {
                "task_id": climate_task["task_id"],
                "verification_run": manual_run,
            }
        ],
    )

    assert event_report["schema_version"] == AUTOMATION_GRADUATION_ACQUISITION_EVENT_REPORT_SCHEMA_VERSION
    assert event_report["summary"]["success_count"] == 1
    assert event_report["summary"]["failed_count"] == 2
    success_event = next(event for event in event_report["events"] if event["status"] == "SUCCESS")
    assert success_event["claim_id"] == "Q10651551|P5991|1"
    assert success_event["evidence_provenance_kind"] == "supplied_acquired_artifact"
    assert success_event["root_artifact_id"] == "manual-climate-root-b"

    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    climate_batch = next(
        batch for batch in merged_batches if batch["family_id"] == "climate_family_safe_reference_transfer_subset"
    )
    assert len(climate_batch["runs"]) == 2

    climate_report = build_nat_claim_convergence_report(climate_batch)
    assert climate_report["summary"]["promoted_count"] == 1
    assert climate_report["summary"]["single_run_count"] == 0
    climate_claim = climate_report["claims"][0]
    assert climate_claim["status"] == "PROMOTED"
    assert climate_claim["independent_count"] == 2


def test_acquisition_runner_rejects_non_independent_manual_artifact() -> None:
    verification_batches = [_load_nat_climate_family_verification_run_fixture()]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    climate_task = task_queue["tasks"][0]
    manual_run = _load_nat_climate_family_manual_acquired_verification_run_fixture()
    manual_run["runs"][0]["root_artifact_id"] = climate_task["required_artifact_contract"][
        "must_be_independent_of_root_artifact_ids"
    ][0]

    event_report = run_nat_acquisition_tasks(
        task_queue,
        [
            {
                "task_id": climate_task["task_id"],
                "verification_run": manual_run,
            }
        ],
    )

    assert event_report["summary"]["success_count"] == 0
    assert event_report["summary"]["failed_count"] == 3
    failure = next(event for event in event_report["events"] if event["route_id"] == climate_task["route_id"])
    assert failure["failure_reason"] == "non_independent_root_artifact"


def test_parthood_family_seed_materializes_distinct_second_family_seed() -> None:
    seed = _load_nat_parthood_family_seed_fixture()

    assert seed["family_id"] == "parthood_family_safe_reference_transfer_subset"
    assert seed["cohort_id"] == "parthood_family_safe_reference_transfer"
    assert seed["candidate_count"] == 3
    assert seed["checked_safe_subset"] == [
        "Q16572|P361|1",
        "Q3700011|P361|1",
        "Q980357|P361|1",
    ]
    assert seed["counts_by_bucket"] == {"safe_with_reference_transfer": 3}
    assert [row["candidate_label"] for row in seed["candidate_profiles"]] == [
        "Guangzhou",
        "kecamatan",
        "grammatical category",
    ]


def test_parthood_family_verification_run_enters_same_hold_path() -> None:
    verification_runs = _load_nat_parthood_family_verification_run_fixture()

    report = build_nat_claim_convergence_report(verification_runs)
    contract = build_nat_confirmation_intake_contract(verification_runs)

    assert report["family_id"] == "parthood_family_safe_reference_transfer_subset"
    assert report["summary"]["total_claims"] == 3
    assert report["summary"]["single_run_count"] == 3
    assert report["summary"]["promoted_count"] == 0
    assert contract["summary"]["intake_request_count"] == 3
    assert all(
        row["suggested_evidence_routes"] == [
            {
                "priority": 1,
                "route_id": f"{row['candidate_id']}:same_family_after_state",
                "route_kind": "same_family_after_state",
                "source_family": "wikidata_migration_pack",
                "why": "A new revision-locked after-state bundle for the same family is the shortest truthful path to independent confirmation.",
            }
        ]
        for row in contract["intake_rows"]
    )
    assert verification_runs["candidate_ids"] == [
        "Q16572|P361|1",
        "Q3700011|P361|1",
        "Q980357|P361|1",
    ]


def test_state_machine_tracks_parthood_as_additional_awaiting_evidence_family() -> None:
    report = build_nat_state_machine_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
            _load_nat_parthood_family_verification_run_fixture(),
        ]
    )

    assert report["summary"]["family_count"] == 3
    assert report["summary"]["promoted_family_count"] == 1
    assert report["summary"]["awaiting_evidence_family_count"] == 1
    assert report["summary"]["migration_pending_family_count"] == 1
    states = {row["family_id"]: row["state"] for row in report["families"]}
    assert states["parthood_family_safe_reference_transfer_subset"] == "AWAITING_EVIDENCE"
    assert states["climate_family_safe_reference_transfer_subset"] == "MIGRATION_PENDING"


def test_migration_batch_finder_selects_only_live_backed_promoted_family() -> None:
    report = build_nat_migration_batch_finder_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
            _load_nat_parthood_family_verification_run_fixture(),
        ]
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_BATCH_FINDER_SCHEMA_VERSION
    assert report["summary"] == {
        "family_count": 3,
        "ready_batch_count": 1,
        "held_family_count": 2,
        "ready_row_count": 2,
        "machine_generated_count": 2,
    }
    ready = report["candidate_batches"][0]
    assert ready["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    assert ready["target_property"] == "P14143"
    assert ready["row_count"] == 2
    held = {row["family_id"]: row for row in report["held_families"]}
    assert held["climate_family_safe_reference_transfer_subset"]["blocking_reason"] == "family_not_promoted"
    assert held["parthood_family_safe_reference_transfer_subset"]["blocking_reason"] == "family_not_promoted"
    machine_generated = report["machine_generated_batches"]
    assert len(machine_generated) == 2
    mg_ids = {row["family_id"] for row in machine_generated}
    assert "climate_family_safe_reference_transfer_subset" in mg_ids
    assert "parthood_family_safe_reference_transfer_subset" in mg_ids


def test_nat_broader_batch_selector_parks_ineligible_families() -> None:
    population = [
        {
            "family_id": "family_ready",
            "cohort_id": "c1",
            "row_count": 10,
            "candidate_ids": ["Q1|P1|1"],
            "state_basis": "baseline_runtime",
        },
        {
            "family_id": "family_parked",
            "cohort_id": "c2",
            "row_count": 8,
            "candidate_ids": ["Q2|P1|1"],
            "state_basis": "baseline_runtime",
            "parked": True,
            "parked_reason": "climate_priority",
        },
        {
            "family_id": "family_tiny",
            "cohort_id": "c3",
            "row_count": 0,
            "candidate_ids": [],
            "state_basis": "mixed_acquisition",
        },
    ]
    selector = build_nat_broader_batch_selector(population, min_row_count=1)
    assert selector["summary"]["candidate_family_count"] == 1
    assert selector["summary"]["parked_family_count"] == 2
    ready = selector["candidate_batches"][0]
    assert ready["family_id"] == "family_ready"
    parked_ids = {row["family_id"] for row in selector["parked_batches"]}
    assert "family_parked" in parked_ids
    assert selector["parked_batches"][0]["parked_reason"] == "climate_priority"


def test_classify_nat_p5991_semantic_bucket_abstains_on_split_shapes() -> None:
    candidate = {
        "candidate_id": "Qsplit|P5991|1",
        "classification": "split_required",
        "model_validation": {
            "status": "model_safe_with_split",
            "resolved_year": "2023",
            "resolved_scope": "TOTAL",
            "resolved_unit_qid": "Q57084755",
            "suggested_action": "migrate_with_split",
            "execution_ready": True,
        },
        "execution_hints": {
            "execution_ready": True,
            "target_property": "P14143",
            "resolved_year": "2023",
            "resolved_scope": "TOTAL",
            "resolved_unit_qid": "Q57084755",
            "execution_backend": "openrefine",
        },
        "claim_bundle_before": {
            "property": "P5991",
            "subject": "Qsplit",
            "value": "+200",
            "qualifiers": {
                "P585": ["+2023-00-00T00:00:00Z"],
                "P518": ["Qpart1", "Qpart2"],
            },
            "references": [{"P854": ["https://example.org/report"]}],
            "rank": "normal",
        },
        "claim_bundle_after": {
            "property": "P14143",
            "subject": "Qsplit",
            "value": "+200",
            "qualifiers": {
                "P585": ["+2023-00-00T00:00:00Z"],
                "P518": ["Qpart1", "Qpart2"],
            },
            "references": [{"P854": ["https://example.org/report"]}],
            "rank": "normal",
        },
    }

    triage = classify_nat_p5991_semantic_bucket(candidate, family_id="business_like_family")

    assert triage["semantic_bucket"] == "split_required"
    assert triage["abstain"] is True
    assert "multi_value_qualifiers_present" in triage["semantic_signals"]
    assert "model_validation:model_safe_with_split" in triage["semantic_signals"]
    assert "deterministic_split_execution_ready" in triage["semantic_signals"]
    assert triage["multi_value_qualifier_properties"] == ["P518"]


def test_nat_p5991_semantic_triage_report_segments_direct_pending_out_of_scope_and_review() -> None:
    review_candidate = {
        "candidate_id": "Qreview|P5991|1",
        "classification": "safe_with_reference_transfer",
        "requires_review": True,
        "claim_bundle_before": {
            "property": "P5991",
            "subject": "Qreview",
            "value": "+55",
            "qualifiers": {},
            "references": [{"P854": ["https://example.org/review"]}],
            "rank": "normal",
        },
        "claim_bundle_after": {
            "property": "P14143",
            "subject": "Qreview",
            "value": "+55",
            "qualifiers": {},
            "references": [{"P854": ["https://example.org/review"]}],
            "rank": "normal",
        },
    }
    review_batch = {
        "family_id": "review_family_safe_subset",
        "cohort_id": "review_family",
        "runs": [
            {
                "migration_pack": {
                    "source_property": "P5991",
                    "target_property": "P14143",
                    "candidates": [review_candidate],
                }
            }
        ],
    }

    triage = build_nat_p5991_semantic_triage_report(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
            _load_nat_parthood_family_verification_run_fixture(),
            review_batch,
        ]
    )

    assert triage["schema_version"] == AUTOMATION_GRADUATION_P5991_SEMANTIC_TRIAGE_SCHEMA_VERSION
    assert triage["summary"]["counts_by_bucket"]["direct_migrate"] == 2
    assert triage["summary"]["counts_by_bucket"]["migration_pending"] == 1
    assert triage["summary"]["counts_by_bucket"]["out_of_scope"] == 3
    assert triage["summary"]["counts_by_bucket"]["needs_review"] == 1
    by_candidate = {row["candidate_id"]: row for row in triage["rows"]}
    assert by_candidate["Q1068745|P5991|1"]["semantic_bucket"] == "direct_migrate"
    assert by_candidate["Q10651551|P5991|1"]["semantic_bucket"] == "migration_pending"
    assert by_candidate["Q16572|P361|1"]["semantic_bucket"] == "out_of_scope"
    assert by_candidate["Qreview|P5991|1"]["semantic_bucket"] == "needs_review"


def test_nat_p5991_semantic_family_selector_only_advances_uniform_direct_migrate_family() -> None:
    selector = build_nat_p5991_semantic_family_selector(
        [
            _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
            _load_nat_climate_family_verification_run_fixture(),
            _load_nat_parthood_family_verification_run_fixture(),
        ],
        min_row_count=1,
    )

    assert selector["schema_version"] == AUTOMATION_GRADUATION_P5991_SEMANTIC_FAMILY_SELECTOR_SCHEMA_VERSION
    assert selector["summary"]["candidate_family_count"] == 1
    candidate = selector["candidate_families"][0]
    assert candidate["family_id"] == "business_family_reconciled_low_qualifier_checked_safe_subset"
    parked = {row["family_id"]: row for row in selector["parked_families"]}
    assert parked["climate_family_safe_reference_transfer_subset"]["parked_reason"] == "migration_pending_rows_present"
    assert parked["parthood_family_safe_reference_transfer_subset"]["parked_reason"] == "out_of_scope_rows_present"


def test_migration_execution_payload_shapes_review_first_rows_for_promoted_family() -> None:
    payload = build_nat_migration_execution_payload(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert payload["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PAYLOAD_SCHEMA_VERSION
    assert payload["payload_status"] == "ready_for_review_payload"
    assert payload["family_state"] == "PROMOTED"
    assert payload["execution_mode"] == "review_first"
    assert payload["summary"]["row_count"] == 2
    assert payload["target_property"] == "P14143"
    assert payload["live_target_supported"] is True
    first_row = payload["openrefine_rows"][0]
    assert first_row["from_property"] == "P5991"
    assert first_row["to_property"] == "P14143"
    assert first_row["classification"] == "safe_with_reference_transfer"
    assert "target_claim_bundle_json" in first_row
    qs_row = payload["quickstatements_v1_rows"][0]
    assert qs_row["property"] == "P14143"
    assert qs_row["subject"].startswith("Q")
    assert qs_row["references"]


def test_migration_execution_payload_consumes_model_aware_split_metadata() -> None:
    verification_runs = copy.deepcopy(_load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture())
    candidate = verification_runs["runs"][0]["migration_pack"]["candidates"][0]
    candidate["classification"] = "model_safe_with_split"
    candidate["model_classification"] = "model_safe_with_split"
    candidate["execution_ready"] = True
    candidate["execution_backend"] = "qs3"
    candidate["model_validation"] = {
        "valid": False,
        "issues": ["split_plan_required"],
        "resolved_year": "2021",
        "resolved_scope": "TOTAL",
        "resolved_unit_qid": "Q57084755",
        "execution_ready": True,
    }
    candidate["split_plan"] = {
        "split_plan_id": "split://Q1068745|P5991|1",
        "status": "execution_ready",
        "suggested_action": "migrate_with_split",
        "reference_propagation": "exact",
        "qualifier_propagation": "exact",
        "resolved_year": "2021",
        "resolved_scope": "TOTAL",
        "resolved_unit_qid": "Q57084755",
        "execution_backend": "qs3",
        "execution_ready": True,
        "proposed_bundle_count": 1,
        "proposed_target_bundles": [candidate["claim_bundle_after"]],
    }
    candidate["execution_profile"] = {"execution_backend": "qs3", "execution_mode": "review_first"}

    payload = build_nat_migration_execution_payload(verification_runs)
    candidate_contracts = build_nat_migration_candidate_contracts(verification_runs)
    backend_plan = build_nat_migration_backend_plan(verification_runs)
    receipt_contract = build_nat_execution_receipt_contract(verification_runs)
    post_write_contract = build_nat_post_write_contract(verification_runs)

    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["model_aware_row_count"] >= 1
    model_row = next(row for row in payload["openrefine_rows"] if row["candidate_id"] == "Q1068745|P5991|1")
    assert model_row["model_classification"] == "model_safe_with_split"
    assert model_row["execution_strategy"] == "split_followthrough"
    assert model_row["execution_backend"] == "qs3"
    assert model_row["model_validation"]["resolved_unit_qid"] == "Q57084755"
    assert model_row["split_plan"]["split_plan_id"] == "split://Q1068745|P5991|1"

    first_contract = next(
        contract for contract in candidate_contracts["candidate_contracts"] if contract["candidate_id"] == "Q1068745|P5991|1"
    )
    assert first_contract["model_validation"]["resolved_year"] == "2021"
    assert first_contract["split_plan"]["suggested_action"] == "migrate_with_split"
    assert first_contract["normalization"]["resolved_scope"] == "TOTAL"

    model_backend_row = next(row for row in backend_plan["backend_rows"] if row["candidate_id"] == "Q1068745|P5991|1")
    assert backend_plan["summary"]["model_aware_count"] >= 1
    assert model_backend_row["execution_backend"] == "qs3"
    assert model_backend_row["model_classification"] == "model_safe_with_split"
    assert model_backend_row["split_plan"]["status"] == "execution_ready"
    assert model_backend_row["quickstatements_row"]["split_plan"]["split_plan_id"] == "split://Q1068745|P5991|1"

    receipt_row = next(row for row in receipt_contract["statement_results"] if row["candidate_id"] == "Q1068745|P5991|1")
    assert "model_classification" in receipt_contract["required_fields"]
    assert receipt_row["model_classification"] == "model_safe_with_split"
    assert receipt_row["split_plan"]["execution_backend"] == "qs3"

    check = next(item for item in post_write_contract["entity_checks"] if item["candidate_id"] == "Q1068745|P5991|1")
    assert "split_plan_match" in check["must_verify"]
    assert "resolved_year_match" in check["must_verify"]
    assert "resolved_scope_match" in check["must_verify"]
    assert "resolved_unit_match" in check["must_verify"]
    assert check["execution_lifecycle_state"] == "ready"


def test_migration_batch_export_pins_review_artifacts_for_business_family() -> None:
    report = build_nat_migration_batch_export(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert report == _load_nat_business_family_migration_batch_export_fixture()
    assert report["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_BATCH_EXPORT_SCHEMA_VERSION
    assert report["export_status"] == "ready_for_review_export"
    assert report["summary"] == {
        "candidate_count": 2,
        "artifact_count": 2,
        "row_count": 2,
        "target_property": "P14143",
    }
    assert [artifact["artifact_kind"] for artifact in report["artifacts"]] == [
        "openrefine_review_rows",
        "quickstatements_v1_review_rows",
    ]


def test_migration_candidate_contracts_capture_pre_execution_business_shape() -> None:
    report = build_nat_migration_candidate_contracts(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_CANDIDATE_CONTRACT_SCHEMA_VERSION
    assert report["summary"] == {
        "candidate_count": 2,
        "target_property": "P14143",
        "counts_by_promotion_class": {
            "review_only": 2,
        },
    }
    first = report["candidate_contracts"][0]
    assert first["candidate_id"] == "Q1068745|P5991|1"
    assert first["source_statement"]["property"] == "P5991"
    assert first["source_statement"]["value"] == {"raw": "100"}
    assert first["target_statement"]["property"] == "P14143"
    assert first["target_statement"]["rank"] == "normal"
    assert first["promotion_class"] == "review_only"
    assert first["promotion_gate"]["decision"] == "review_only"
    assert first["normalization"]["year_basis"] == "point_in_time"
    assert first["normalization"]["quantity_unit_normalized"] is False


def test_migration_candidate_contracts_surface_subject_resolution_gate_and_distribution() -> None:
    verification_runs = copy.deepcopy(_load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture())
    candidates = verification_runs["runs"][0]["migration_pack"]["candidates"]
    for candidate in candidates:
        candidate["promotion_class"] = "full_auto"
        candidate["promotion_gate"] = {
            "decision": "full_auto",
            "reason": "subject_resolution_ready",
            "eligibility": {
                "eligible": True,
                "review_only": False,
                "semi_auto": True,
                "full_auto": True,
            },
        }

    candidates[0]["subject_resolution"] = {
        "status": "known",
        "subject_family": "company",
        "instance_of_allowed": True,
    }
    candidates[1]["subject_resolution"] = {
        "status": "unknown",
    }

    report = build_nat_migration_candidate_contracts(verification_runs)

    assert report["summary"]["subject_resolution_counts"] == {
        "known": 1,
        "unknown": 1,
        "absent": 0,
    }
    assert report["summary"]["subject_resolution_allowed_count"] == 1
    assert report["summary"]["subject_resolution_blocked_count"] == 1
    assert report["summary"]["subject_resolution_gate_ready"] is False
    assert report["summary"]["subject_resolution_distribution_by_promotion_class"] == {
        "full_auto": {
            "absent": 0,
            "known": 1,
            "unknown": 1,
        }
    }

    known_candidate = next(
        contract for contract in report["candidate_contracts"] if contract["candidate_id"] == "Q1068745|P5991|1"
    )
    unknown_candidate = next(
        contract for contract in report["candidate_contracts"] if contract["candidate_id"] == "Q1489170|P5991|1"
    )

    assert known_candidate["subject_resolution"]["status"] == "known"
    assert known_candidate["promotion_gate"]["eligibility"]["instance_of_allowed"] is True
    assert known_candidate["promotion_gate"]["readiness"]["ready"] is True
    assert "subject_resolution_unknown" not in known_candidate["promotion_gate"]["readiness"]["hard_defects"]

    assert unknown_candidate["subject_resolution"]["status"] == "unknown"
    assert unknown_candidate["promotion_gate"]["eligibility"]["instance_of_allowed"] is False
    assert unknown_candidate["promotion_gate"]["eligibility"]["eligible"] is False
    assert unknown_candidate["promotion_gate"]["decision"] == "review_only"
    assert unknown_candidate["promotion_gate"]["readiness"]["ready"] is False
    assert "subject_resolution_unknown" in unknown_candidate["promotion_gate"]["readiness"]["hard_defects"]


def test_migration_backend_plan_routes_normal_rows_to_openrefine() -> None:
    plan = build_nat_migration_backend_plan(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert plan["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_BACKEND_PLAN_SCHEMA_VERSION
    assert plan["summary"] == {
        "candidate_count": 2,
        "openrefine_count": 2,
        "qs3_count": 0,
    }
    assert {row["execution_backend"] for row in plan["backend_rows"]} == {"openrefine"}


def test_migration_backend_plan_routes_non_normal_rank_rows_to_qs3() -> None:
    verification_runs = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    candidate = verification_runs["runs"][0]["migration_pack"]["candidates"][0]
    candidate["claim_bundle_after"]["rank"] = "preferred"

    plan = build_nat_migration_backend_plan(verification_runs)

    assert plan["summary"]["openrefine_count"] == 1
    assert plan["summary"]["qs3_count"] == 1
    preferred_row = next(row for row in plan["backend_rows"] if row["candidate_id"] == "Q1068745|P5991|1")
    assert preferred_row["execution_backend"] == "qs3"
    assert preferred_row["quickstatements_row"]["rank"] == "preferred"


def test_execution_receipt_contract_stays_template_until_external_run_occurs() -> None:
    receipt = build_nat_execution_receipt_contract(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert receipt["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_RECEIPT_CONTRACT_SCHEMA_VERSION
    assert receipt["receipt_status"] == "awaiting_external_execution_receipt"
    assert receipt["summary"] == {
        "candidate_count": 2,
        "backend_count": 1,
    }
    assert all(row["execution_status"] == "awaiting_external_execution" for row in receipt["statement_results"])


def test_post_write_contract_requires_observed_after_state_fields() -> None:
    report = build_nat_post_write_contract(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_POST_WRITE_CONTRACT_SCHEMA_VERSION
    assert report["verification_status"] == "awaiting_observed_after_state"
    assert report["execution_lifecycle_contract"] == {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "state_order": ["not_started", "ready", "executed", "verified"],
        "current_state": "ready",
        "promotion_status": "hold",
        "fail_closed_on_mismatch": True,
        "eligible_row_count": 2,
        "verified_row_count": 0,
        "executed_row_count": 0,
    }
    assert report["verification_contract"] == {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "verification_status": "awaiting_observed_after_state",
        "required_observed_fields": [
            "candidate_id",
            "entity_qid",
            "after_state_value",
            "after_state_references",
            "after_state_qualifiers",
        ],
        "fail_closed_on_mismatch": True,
    }
    assert report["summary"] == {
        "candidate_count": 2,
        "required_verification_fields": 5,
    }
    assert report["entity_checks"][0]["must_verify"] == [
        "target_found",
        "value_match",
        "qualifier_match",
        "reference_match",
        "rank_match",
    ]
    assert report["entity_checks"][0]["execution_lifecycle_state"] == "ready"


def test_migration_simulation_contract_owns_the_full_pre_execution_loop() -> None:
    contract = build_nat_migration_simulation_contract(
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    )

    assert contract["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_SIMULATION_CONTRACT_SCHEMA_VERSION
    assert contract["simulation_status"] == "ready_for_external_execution"
    assert contract["summary"] == {
        "candidate_count": 2,
        "openrefine_count": 2,
        "qs3_count": 0,
        "counts_by_promotion_class": {
            "review_only": 2,
        },
    }
    assert contract["readiness_contract"] == {
        "promotion_status": "hold",
        "execution_lifecycle_state": "ready",
        "post_write_verification_status": "awaiting_observed_after_state",
        "review_first": True,
        "ready_for_external_execution": True,
    }
    assert contract["candidate_contracts"]["summary"]["candidate_count"] == 2
    assert contract["receipt_contract"]["receipt_status"] == "awaiting_external_execution_receipt"
    assert contract["post_write_contract"]["verification_status"] == "awaiting_observed_after_state"


def test_subject_resolution_metrics_flow_through_post_write_and_simulation_surfaces() -> None:
    verification_runs = copy.deepcopy(_load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture())
    candidates = verification_runs["runs"][0]["migration_pack"]["candidates"]
    for candidate in candidates:
        candidate["promotion_class"] = "full_auto"
        candidate["promotion_gate"] = {
            "decision": "full_auto",
            "reason": "subject_resolution_ready",
            "eligibility": {
                "eligible": True,
                "review_only": False,
                "semi_auto": True,
                "full_auto": True,
            },
        }

    candidates[0]["subject_resolution"] = {
        "status": "known",
        "subject_family": "company",
        "instance_of_allowed": True,
    }
    candidates[1]["subject_resolution"] = {
        "status": "unknown",
    }

    post_write = build_nat_post_write_contract(verification_runs)
    simulation = build_nat_migration_simulation_contract(verification_runs)

    expected_counts = {
        "known": 1,
        "unknown": 1,
        "absent": 0,
    }

    assert post_write["summary"]["subject_resolution_counts"] == expected_counts
    assert post_write["summary"]["subject_resolution_gate_ready"] is False
    assert post_write["readiness_surface"]["subject_resolution_counts"] == expected_counts
    assert post_write["readiness_surface"]["subject_resolution_gate_ready"] is False
    assert post_write["readiness_surface"]["ready_for_external_execution"] is False
    assert post_write["pilot_metrics"]["subject_resolution_counts"] == expected_counts
    assert post_write["pilot_metrics"]["subject_resolution_gate_ready"] is False
    assert post_write["pilot_metrics"]["subject_resolution_hard_defect_count"] == 1
    assert all("subject_resolution_match" in item["must_verify"] for item in post_write["entity_checks"])

    assert simulation["summary"]["subject_resolution_counts"] == expected_counts
    assert simulation["summary"]["subject_resolution_distribution_by_promotion_class"] == {
        "full_auto": {
            "absent": 0,
            "known": 1,
            "unknown": 1,
        }
    }
    assert simulation["readiness_contract"]["subject_resolution_counts"] == expected_counts
    assert simulation["readiness_contract"]["subject_resolution_gate_ready"] is False
    assert simulation["readiness_contract"]["ready_for_external_execution"] is False


def test_migration_executed_rows_are_derived_from_export_artifact() -> None:
    batch_export = _load_nat_business_family_migration_batch_export_fixture()

    executed = build_nat_migration_executed_rows(batch_export)

    assert executed == _load_nat_business_family_migration_executed_rows_fixture()
    assert executed["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_EXECUTED_ROWS_SCHEMA_VERSION
    assert executed["execution_status"] == "ready_execution_receipts"
    assert executed["summary"] == {
        "row_count": 2,
        "artifact_count": 4,
    }
    assert executed["executed_rows"][0]["artifact_kinds"] == [
        "openrefine_review_rows",
        "quickstatements_v1_review_rows",
    ]


def test_migration_execution_payload_blocks_synthetic_target_family_even_when_promoted() -> None:
    verification_batches = [
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
        _load_nat_parthood_family_verification_run_fixture(),
    ]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    first_manual_run = _load_nat_parthood_family_manual_acquired_verification_run_fixture()
    remaining_manual_run = _load_nat_parthood_family_manual_acquired_remaining_verification_run_fixture()
    supplied = []
    first_task = next(task for task in task_queue["tasks"] if task["candidate_id"] == "Q16572|P361|1")
    supplied.append({"task_id": first_task["task_id"], "verification_run": first_manual_run})
    for candidate_id in ["Q3700011|P361|1", "Q980357|P361|1"]:
        task = next(task for task in task_queue["tasks"] if task["candidate_id"] == candidate_id)
        supplied.append({"task_id": task["task_id"], "verification_run": remaining_manual_run})
    event_report = run_nat_acquisition_tasks(task_queue, supplied)
    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    parthood_batch = next(
        batch for batch in merged_batches if batch["family_id"] == "parthood_family_safe_reference_transfer_subset"
    )

    payload = build_nat_migration_execution_payload(parthood_batch)

    assert payload["family_state"] == "PROMOTED"
    assert payload["payload_status"] == "target_property_not_live_backed"
    assert payload["target_property"] == "P99999"
    assert payload["live_target_supported"] is False
    assert payload["summary"]["row_count"] == 3


def test_migration_lifecycle_report_tracks_ready_executed_and_verified() -> None:
    business_batch = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()
    lifecycle_ready = build_nat_migration_lifecycle_report([business_batch])

    assert lifecycle_ready["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_LIFECYCLE_REPORT_SCHEMA_VERSION
    assert lifecycle_ready["summary"] == {
        "ready_count": 1,
        "executed_count": 0,
        "verified_count": 0,
        "not_started_count": 0,
    }
    assert lifecycle_ready["families"][0]["lifecycle_state"] == "READY"

    executed_rows = _load_nat_business_family_migration_executed_rows_fixture()["executed_rows"]
    lifecycle_executed = build_nat_migration_lifecycle_report(
        [business_batch],
        executed_rows=executed_rows,
    )
    assert lifecycle_executed["summary"] == {
        "ready_count": 0,
        "executed_count": 1,
        "verified_count": 0,
        "not_started_count": 0,
    }
    assert lifecycle_executed["families"][0]["lifecycle_state"] == "EXECUTED"

    lifecycle_verified = build_nat_migration_lifecycle_report(
        [business_batch],
        executed_rows=executed_rows,
        post_execution_batches=[business_batch],
    )
    assert lifecycle_verified["summary"] == {
        "ready_count": 0,
        "executed_count": 0,
        "verified_count": 1,
        "not_started_count": 0,
    }
    assert lifecycle_verified["families"][0]["lifecycle_state"] == "VERIFIED"


def test_build_nat_migration_executed_rows_prefers_execution_receipts() -> None:
    proof = _load_nat_business_family_migration_execution_proof_fixture()
    rows = build_nat_migration_executed_rows(proof["batch_export"])
    assert rows == proof["executed_rows_report"]


def test_migration_execution_proof_bundle_carries_business_family_to_verified() -> None:
    business_batch = _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture()

    proof = build_nat_migration_execution_proof(
        business_batch,
        post_execution_batches=[business_batch],
    )

    assert proof == _load_nat_business_family_migration_execution_proof_fixture()
    assert proof["schema_version"] == AUTOMATION_GRADUATION_MIGRATION_EXECUTION_PROOF_SCHEMA_VERSION
    assert proof["summary"] == {
        "export_status": "ready_for_review_export",
        "execution_status": "ready_execution_receipts",
        "lifecycle_state": "VERIFIED",
        "candidate_count": 2,
    }


def test_parthood_family_acquisition_plan_prioritizes_archetypal_candidates_honestly() -> None:
    verification_runs = _load_nat_parthood_family_verification_run_fixture()
    expected = _load_nat_parthood_family_acquisition_plan_fixture()

    report = build_nat_family_acquisition_plan(verification_runs)

    assert report == expected
    assert report["schema_version"] == AUTOMATION_GRADUATION_FAMILY_ACQUISITION_PLAN_SCHEMA_VERSION
    assert report["family_id"] == "parthood_family_safe_reference_transfer_subset"
    assert report["family_state"] == "AWAITING_EVIDENCE"
    assert report["family_kind"] == "concrete_candidate_family"
    assert report["summary"]["candidate_count"] == 3
    assert report["summary"]["placeholder_candidate_count"] == 0
    assert report["summary"]["top_priority_candidate_id"] == "Q16572|P361|1"
    assert [row["candidate_archetype"] for row in report["candidate_plans"]] == [
        "city_or_municipality",
        "district_or_subdivision",
        "class_or_type_ontology",
    ]
    assert [row["priority"] for row in report["candidate_plans"]] == [1, 2, 3]
    assert [row["candidate_label"] for row in report["candidate_plans"]] == [
        "Guangzhou",
        "kecamatan",
        "grammatical category",
    ]


def test_same_family_after_state_acquisition_fails_on_current_parthood_live_entity_export() -> None:
    verification_runs = _load_nat_parthood_family_verification_run_fixture()
    task_queue = build_nat_acquisition_task_queue([verification_runs])
    top_task = next(task for task in task_queue["tasks"] if task["candidate_id"] == "Q16572|P361|1")

    event_report = run_nat_same_family_after_state_acquisition_tasks(
        {"tasks": [top_task]},
        [verification_runs],
        [
            {
                "task_id": top_task["task_id"],
                "entity_export_payload": _load_nat_parthood_live_q16572_entity_export_fixture(),
                "run_id": "run-2026-04-04-parthood-live-current",
                "batch_id": "nat-parthood-live-current",
                "window_id": "after-parthood-live-current",
            }
        ],
    )

    assert event_report["summary"]["success_count"] == 0
    assert event_report["summary"]["failed_count"] == 1
    assert event_report["events"][0]["candidate_id"] == "Q16572|P361|1"
    assert event_report["events"][0]["failure_reason"] == "verification_target_missing"


def test_same_family_after_state_acquisition_scan_fails_for_all_current_parthood_live_candidates() -> None:
    verification_runs = _load_nat_parthood_family_verification_run_fixture()
    expected = _load_nat_parthood_live_acquisition_scan_fixture()
    task_queue = build_nat_acquisition_task_queue([verification_runs])
    live_exports = [
        (
            "Q16572|P361|1",
            _load_nat_parthood_live_q16572_entity_export_fixture(),
        ),
        (
            "Q3700011|P361|1",
            {
                "_source_revision": 2475626330,
                "entities": {
                    "Q3700011": {
                        "claims": {
                            "P361": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "property": "P361",
                                        "hash": "c34cc810af1645c38b65172df5ea49c7d9a4b74c",
                                        "datavalue": {
                                            "value": {
                                                "entity-type": "item",
                                                "numeric-id": 3199141,
                                                "id": "Q3199141"
                                            },
                                            "type": "wikibase-entityid"
                                        },
                                        "datatype": "wikibase-item"
                                    },
                                    "type": "statement",
                                    "id": "Q3700011$bd1211b8-4835-a38e-1fab-35f26fd0c576",
                                    "rank": "normal",
                                    "references": [
                                        {
                                            "hash": "614ad792db65f4832704e0d758747a736d6fce38",
                                            "snaks": {
                                                "P248": [
                                                    {
                                                        "snaktype": "value",
                                                        "property": "P248",
                                                        "hash": "ebeb1a5fd833a49e1fb942e4e3bc7a52605f08f1",
                                                        "datavalue": {
                                                            "value": {
                                                                "entity-type": "item",
                                                                "numeric-id": 129566940,
                                                                "id": "Q129566940"
                                                            },
                                                            "type": "wikibase-entityid"
                                                        },
                                                        "datatype": "wikibase-item"
                                                    }
                                                ],
                                                "P958": [
                                                    {
                                                        "snaktype": "value",
                                                        "property": "P958",
                                                        "hash": "2a06eb868e486e4cf9d01659a66f7296143c4054",
                                                        "datavalue": {
                                                            "value": "Pasal 66 ayat (1)",
                                                            "type": "string"
                                                        },
                                                        "datatype": "string"
                                                    }
                                                ],
                                                "P1683": [
                                                    {
                                                        "snaktype": "value",
                                                        "property": "P1683",
                                                        "hash": "c8c340b8107e07af788a4d047c19901ed297bd17",
                                                        "datavalue": {
                                                            "value": {
                                                                "text": "Kecamatan merupakan perangkat Daerah Kabupaten dan Daerah Kota yang dipimpin oleh Kepala Kecamatan",
                                                                "language": "id"
                                                            },
                                                            "type": "monolingualtext"
                                                        },
                                                        "datatype": "monolingualtext"
                                                    }
                                                ]
                                            },
                                            "snaks-order": ["P248", "P958", "P1683"]
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            },
        ),
        (
            "Q980357|P361|1",
            {
                "_source_revision": 2474581003,
                "entities": {
                    "Q980357": {
                        "claims": {
                            "P361": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "property": "P361",
                                        "hash": "0452c7fdd92182d232939f0376ae44e2bb1f3dc7",
                                        "datavalue": {
                                            "value": {
                                                "entity-type": "item",
                                                "numeric-id": 315,
                                                "id": "Q315"
                                            },
                                            "type": "wikibase-entityid"
                                        },
                                        "datatype": "wikibase-item"
                                    },
                                    "type": "statement",
                                    "id": "Q980357$b1e12140-47c6-486f-3272-5138cf092942",
                                    "rank": "normal",
                                    "references": [
                                        {
                                            "hash": "9b5d9b4536201a9e9fc5b1773cf217caee155ec2",
                                            "snaks": {
                                                "P854": [
                                                    {
                                                        "snaktype": "value",
                                                        "property": "P854",
                                                        "hash": "c8f26e5b4d0e202679c53a06cb9c669b4dfe923c",
                                                        "datavalue": {
                                                            "value": "http://www-01.sil.org/linguistics/GlossaryOflinguisticTerms/WhatIsAGrammaticalCategory.htm",
                                                            "type": "string"
                                                        },
                                                        "datatype": "url"
                                                    }
                                                ],
                                                "P813": [
                                                    {
                                                        "snaktype": "value",
                                                        "property": "P813",
                                                        "hash": "9732ec7ca2833afeb3e14a500973d76429717655",
                                                        "datavalue": {
                                                            "value": {
                                                                "time": "+2015-10-11T00:00:00Z",
                                                                "timezone": 0,
                                                                "before": 0,
                                                                "after": 0,
                                                                "precision": 11,
                                                                "calendarmodel": "http://www.wikidata.org/entity/Q1985727"
                                                            },
                                                            "type": "time"
                                                        },
                                                        "datatype": "time"
                                                    }
                                                ]
                                            },
                                            "snaks-order": ["P854", "P813"]
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            },
        ),
    ]
    supplied = []
    for candidate_id, entity_export_payload in live_exports:
        task = next(task for task in task_queue["tasks"] if task["candidate_id"] == candidate_id)
        supplied.append(
            {
                "task_id": task["task_id"],
                "entity_export_payload": entity_export_payload,
                "run_id": f"live-scan-{candidate_id.split('|', 1)[0]}",
                "batch_id": "nat-parthood-live-scan",
                "window_id": f"after-live-{candidate_id.split('|', 1)[0].lower()}",
            }
        )

    report = run_nat_same_family_after_state_acquisition_tasks(
        task_queue,
        [verification_runs],
        supplied,
    )

    assert report == expected


def test_acquisition_runner_accepts_manual_parthood_artifact_and_marks_family_ready_to_rerun() -> None:
    verification_batches = [
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
        _load_nat_parthood_family_verification_run_fixture(),
    ]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    parthood_task = next(task for task in task_queue["tasks"] if task["candidate_id"] == "Q16572|P361|1")
    manual_run = _load_nat_parthood_family_manual_acquired_verification_run_fixture()

    event_report = run_nat_acquisition_tasks(
        task_queue,
        [
            {
                "task_id": parthood_task["task_id"],
                "verification_run": manual_run,
            }
        ],
    )

    assert event_report["summary"]["success_count"] == 1
    assert event_report["summary"]["failed_count"] == 2
    success_event = next(event for event in event_report["events"] if event["status"] == "SUCCESS")
    assert success_event["claim_id"] == "Q16572|P361|1"
    assert success_event["root_artifact_id"] == "manual-parthood-root-b"

    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    parthood_batch = next(
        batch for batch in merged_batches if batch["family_id"] == "parthood_family_safe_reference_transfer_subset"
    )
    assert len(parthood_batch["runs"]) == 2

    parthood_report = build_nat_claim_convergence_report(parthood_batch)
    assert parthood_report["summary"]["promoted_count"] == 1
    assert parthood_report["summary"]["single_run_count"] == 2
    promoted_claim = next(
        claim for claim in parthood_report["claims"] if claim["claim_id"] == "Q16572|P361|1"
    )
    assert promoted_claim["status"] == "PROMOTED"
    assert promoted_claim["independent_count"] == 2

    state_report = build_nat_state_machine_report(
        verification_batches,
        acquisition_events=event_report["events"],
    )
    rows = {row["family_id"]: row for row in state_report["families"]}
    assert rows["parthood_family_safe_reference_transfer_subset"]["state"] == "READY_TO_RERUN"
    assert rows["parthood_family_safe_reference_transfer_subset"]["state_basis"] == "supplied_acquired_artifact"


def test_parthood_family_promotes_when_all_missing_claims_receive_manual_independent_artifacts() -> None:
    verification_batches = [
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
        _load_nat_parthood_family_verification_run_fixture(),
    ]
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    first_manual_run = _load_nat_parthood_family_manual_acquired_verification_run_fixture()
    remaining_manual_run = _load_nat_parthood_family_manual_acquired_remaining_verification_run_fixture()

    supplied = []
    first_task = next(task for task in task_queue["tasks"] if task["candidate_id"] == "Q16572|P361|1")
    supplied.append({"task_id": first_task["task_id"], "verification_run": first_manual_run})
    for candidate_id in ["Q3700011|P361|1", "Q980357|P361|1"]:
        task = next(task for task in task_queue["tasks"] if task["candidate_id"] == candidate_id)
        supplied.append({"task_id": task["task_id"], "verification_run": remaining_manual_run})

    event_report = run_nat_acquisition_tasks(task_queue, supplied)

    assert event_report["summary"]["success_count"] == 3
    assert event_report["summary"]["failed_count"] == 0

    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    parthood_batch = next(
        batch for batch in merged_batches if batch["family_id"] == "parthood_family_safe_reference_transfer_subset"
    )
    assert len(parthood_batch["runs"]) == 4

    parthood_report = build_nat_claim_convergence_report(parthood_batch)
    assert parthood_report["summary"]["promoted_count"] == 3
    assert parthood_report["summary"]["single_run_count"] == 0
    assert all(claim["status"] == "PROMOTED" for claim in parthood_report["claims"])

    state_report = build_nat_state_machine_report(merged_batches)
    rows = {row["family_id"]: row for row in state_report["families"]}
    assert rows["parthood_family_safe_reference_transfer_subset"]["state"] == "PROMOTED"
    assert rows["parthood_family_safe_reference_transfer_subset"]["state_basis"] == "supplied_acquired_artifact"
    assert state_report["summary"]["promoted_family_count_by_basis"] == {
        "baseline_runtime": 1,
        "supplied_acquired_artifact": 1,
    }


def test_live_same_family_acquisition_sweep_can_promote_parthood_with_independent_live_exports() -> None:
    verification_batches = [
        _load_nat_cohort_a_gate_b_candidate_verification_runs_ready_fixture(),
        _load_nat_parthood_family_verification_run_fixture(),
    ]
    parthood_batch = _load_nat_parthood_family_verification_run_fixture()
    task_queue = build_nat_acquisition_task_queue(verification_batches)
    acquisition_plan = build_nat_family_acquisition_plan(parthood_batch)

    run_by_candidate = {}
    for run in parthood_batch["runs"]:
        for candidate in run["migration_pack"]["candidates"]:
            run_by_candidate[candidate["candidate_id"]] = candidate

    revision_map = {
        "Q16572": [{"revid": 2476000101, "timestamp": "2026-04-05T00:00:00Z"}],
        "Q3700011": [{"revid": 2476000102, "timestamp": "2026-04-05T00:01:00Z"}],
        "Q980357": [{"revid": 2476000103, "timestamp": "2026-04-05T00:02:00Z"}],
    }
    export_map = {
        ("Q16572", 2476000101): _entity_export_from_candidate(
            {
                **run_by_candidate["Q16572|P361|1"],
                "claim_bundle_before": {
                    **run_by_candidate["Q16572|P361|1"]["claim_bundle_before"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:00:00Z"],
                            "P854": ["https://example.org/live-parthood/guangzhou-second-snapshot"],
                        }
                    ],
                },
                "claim_bundle_after": {
                    **run_by_candidate["Q16572|P361|1"]["claim_bundle_after"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:00:00Z"],
                            "P854": ["https://example.org/live-parthood/guangzhou-second-snapshot"],
                        }
                    ],
                },
            },
            revision_id=2476000101,
        ),
        ("Q3700011", 2476000102): _entity_export_from_candidate(
            {
                **run_by_candidate["Q3700011|P361|1"],
                "claim_bundle_before": {
                    **run_by_candidate["Q3700011|P361|1"]["claim_bundle_before"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:01:00Z"],
                            "P854": ["https://example.org/live-parthood/kecamatan-second-snapshot"],
                        }
                    ],
                },
                "claim_bundle_after": {
                    **run_by_candidate["Q3700011|P361|1"]["claim_bundle_after"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:01:00Z"],
                            "P854": ["https://example.org/live-parthood/kecamatan-second-snapshot"],
                        }
                    ],
                },
            },
            revision_id=2476000102,
        ),
        ("Q980357", 2476000103): _entity_export_from_candidate(
            {
                **run_by_candidate["Q980357|P361|1"],
                "claim_bundle_before": {
                    **run_by_candidate["Q980357|P361|1"]["claim_bundle_before"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:02:00Z"],
                            "P854": ["https://example.org/live-parthood/grammar-second-snapshot"],
                        }
                    ],
                },
                "claim_bundle_after": {
                    **run_by_candidate["Q980357|P361|1"]["claim_bundle_after"],
                    "references": [
                        {
                            "P813": ["+2026-04-05T00:02:00Z"],
                            "P854": ["https://example.org/live-parthood/grammar-second-snapshot"],
                        }
                    ],
                },
            },
            revision_id=2476000103,
        ),
    }

    def _fetch_recent_revisions(entity_qid: str, *, revision_limit: int = 10, timeout_seconds: int = 30) -> list[dict]:
        assert revision_limit == 10
        assert timeout_seconds == 30
        return revision_map[entity_qid]

    def _fetch_entity_export(entity_qid: str, revision_id: int | str, *, timeout_seconds: int = 30) -> dict:
        assert timeout_seconds == 30
        return export_map[(entity_qid, int(revision_id))]

    event_report = run_nat_live_same_family_acquisition_sweep(
        task_queue,
        verification_batches,
        acquisition_plan,
        stop_on_first_success=False,
        fetch_recent_revisions_fn=_fetch_recent_revisions,
        fetch_entity_export_fn=_fetch_entity_export,
    )

    assert event_report["summary"]["success_count"] == 3
    assert event_report["summary"]["failed_count"] == 0
    assert {
        event["candidate_id"] for event in event_report["events"] if event["status"] == "SUCCESS"
    } == {"Q16572|P361|1", "Q3700011|P361|1", "Q980357|P361|1"}
    assert all(
        event["evidence_provenance_kind"] == "live_same_family_acquisition"
        for event in event_report["events"]
        if event["status"] == "SUCCESS"
    )

    merged_batches = merge_nat_acquired_evidence(verification_batches, event_report)
    state_report = build_nat_state_machine_report(merged_batches)
    rows = {row["family_id"]: row for row in state_report["families"]}
    assert rows["parthood_family_safe_reference_transfer_subset"]["state"] == "PROMOTED"
    assert rows["parthood_family_safe_reference_transfer_subset"]["state_basis"] == "live_same_family_acquisition"
    assert state_report["summary"]["promoted_family_count_by_basis"] == {
        "baseline_runtime": 1,
        "live_same_family_acquisition": 1,
    }


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


def test_post_write_verification_report_marks_verified_runs() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    report = build_nat_post_write_verification_report(runs)

    assert report["schema_version"] == AUTOMATION_GRADUATION_POST_WRITE_VERIFICATION_SCHEMA_VERSION
    assert report["execution_lifecycle_contract"] == {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "state_order": ["not_started", "ready", "executed", "verified"],
        "current_state": "verified",
        "promotion_status": "ready",
        "fail_closed_on_mismatch": True,
        "run_count": len(runs),
        "verified_run_count": len(runs),
    }
    assert report["verification_contract"] == {
        "schema_version": AUTOMATION_GRADUATION_POST_WRITE_LIFECYCLE_CONTRACT_SCHEMA_VERSION,
        "verification_status": "verified",
        "require_all_verified": True,
        "fail_closed_on_mismatch": True,
        "promotion_status": "ready",
    }
    assert report["summary"]["run_count"] == len(runs)
    assert report["summary"]["verified_run_count"] == len(runs)
    assert report["summary"]["verification_ready"] is True
    assert report["subject_aware_summary"]["uses_subject_resolution"] is False
    assert report["subject_aware_summary"]["subject_count"] == 2
    assert report["subject_aware_summary"]["verified_subject_count"] == 2
    assert report["subject_aware_summary"]["subject_aware_ready"] is True
    assert all(row["verification_status"] == "verified" for row in report["runs"])
    assert all(row["lifecycle_state"] == "verified" for row in report["runs"])
    assert all(row["promotion_status"] == "ready" for row in report["runs"])


def test_post_write_verification_report_detects_drifts() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    drift_run = copy.deepcopy(runs[0])
    drift_run["run_id"] = "run-drift"
    drift_run["batch_id"] = "batch-drift"
    drift_run["after_payload"] = {"windows": [{"id": "drift", "statement_bundles": []}]}

    report = build_nat_post_write_verification_report([drift_run], require_all_verified=True)
    assert report["summary"]["run_count"] == 1
    assert report["summary"]["verified_run_count"] == 0
    assert report["summary"]["verification_ready"] is False
    assert report["execution_lifecycle_contract"]["current_state"] == "executed"
    assert report["execution_lifecycle_contract"]["promotion_status"] == "hold"
    assert report["verification_contract"]["verification_status"] == "verification_drift"
    assert report["verification_contract"]["promotion_status"] == "hold"
    assert report["summary"]["pending_drifts"] == ["run-drift"]
    assert report["runs"][0]["verification_status"] == "verification_drift"
    assert report["runs"][0]["lifecycle_state"] == "executed"
    assert report["runs"][0]["promotion_status"] == "hold"
    assert report["runs"][0]["counts_by_status"].get("target_missing", 0) >= 1


def test_post_write_verification_report_falls_back_when_only_unknown_subject_resolution_is_present() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    run = copy.deepcopy(runs[0])
    candidate = run["migration_pack"]["candidates"][0]
    candidate["subject_resolution"] = {
        "schema_version": "sl.wikidata_subject_resolution.v0_1",
        "status": "unresolved",
        "subject_family": "unknown",
        "resolution_basis": "no_typed_evidence",
        "window_id": "t2",
        "direct_instance_of": [],
        "resolved_via": None,
        "matched_type_qids": [],
        "traversed_subclass_of": [],
        "evidence": [],
    }
    report = build_nat_post_write_verification_report([run])

    assert report["subject_aware_summary"]["uses_subject_resolution"] is False
    assert report["subject_aware_summary"]["unknown_subject_count"] == report["subject_aware_summary"]["subject_count"]
    assert report["subject_aware_summary"]["subject_aware_ready"] is True


def test_post_write_verification_report_requires_verified_company_subjects_when_typed() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    company_run = copy.deepcopy(runs[0])
    company_run["migration_pack"]["candidates"][0]["subject_resolution"] = {
        "schema_version": "sl.wikidata_subject_resolution.v0_1",
        "status": "resolved",
        "subject_family": "company",
        "resolution_basis": "typed_evidence",
        "window_id": "t2",
        "direct_instance_of": ["Q6881511"],
        "resolved_via": "p31_p279_chain",
        "matched_type_qids": ["Q6881511"],
        "traversed_subclass_of": [],
        "evidence": [{"property": "P31", "subject_qid": "Q309865", "value_qid": "Q6881511", "window_id": "t2"}],
    }
    unknown_run = copy.deepcopy(runs[1])
    unknown_run["migration_pack"]["candidates"][0]["subject_resolution"] = {
        "schema_version": "sl.wikidata_subject_resolution.v0_1",
        "status": "unresolved",
        "subject_family": "unknown",
        "resolution_basis": "typed_evidence_not_mapped",
        "window_id": "t2",
        "direct_instance_of": ["Q999999"],
        "resolved_via": None,
        "matched_type_qids": [],
        "traversed_subclass_of": [],
        "evidence": [{"property": "P31", "subject_qid": "Q10403939", "value_qid": "Q999999", "window_id": "t2"}],
    }

    report = build_nat_post_write_verification_report([company_run, unknown_run])

    assert report["subject_aware_summary"]["uses_subject_resolution"] is True
    assert report["subject_aware_summary"]["company_subject_count"] == 1
    assert report["subject_aware_summary"]["verified_company_subject_count"] == 1
    assert report["subject_aware_summary"]["unknown_subject_count"] == 1
    assert report["subject_aware_summary"]["subject_aware_ready"] is False
    assert report["subject_aware_summary"]["subject_aware_state"] == "executed"


def test_sandbox_post_write_verification_report_marks_verified_rows() -> None:
    sandbox_packet = {
        "packet_id": "nat-sandbox-packet",
        "target_item": {"qid": "Q4115189"},
        "rows": [
            {
                "row_id": "sandbox-row-1",
                "subject": "Q4115189",
                "expected_after_state": {
                    "subject": "Q4115189",
                    "property": "P14143",
                    "value": "+13",
                    "unit_qid": "Q57084755",
                    "rank": "normal",
                    "qualifiers": {"P585": ["+2024-00-00T00:00:00Z"]},
                    "references": [{"P854": ["https://www.wikidata.org/wiki/Property:P14143"]}],
                },
            }
        ],
    }
    observed_after_state = {
        "capture_id": "sandbox-capture-1",
        "target_item": "Q4115189",
        "observed_rows": [
            {
                "row_id": "sandbox-row-1",
                "observed": {
                    "subject": "Q4115189",
                    "property": "P14143",
                    "value": "+13",
                    "unit_qid": "Q57084755",
                    "rank": "normal",
                    "qualifiers": {"P585": ["+2024-00-00T00:00:00Z"]},
                    "references": [{"P854": ["https://www.wikidata.org/wiki/Property:P14143"]}],
                },
            }
        ],
    }

    report = build_nat_sandbox_post_write_verification_report(
        sandbox_packet,
        observed_after_state,
    )

    assert report["schema_version"] == AUTOMATION_GRADUATION_POST_WRITE_VERIFICATION_SCHEMA_VERSION
    assert report["sandbox_packet_id"] == "nat-sandbox-packet"
    assert report["observed_capture_id"] == "sandbox-capture-1"
    assert report["summary"]["run_count"] == 1
    assert report["summary"]["verified_run_count"] == 1
    assert report["summary"]["verification_ready"] is True
    assert report["sandbox_summary"]["packet_row_count"] == 1
    assert report["sandbox_summary"]["observed_row_count"] == 1
    assert report["runs"][0]["counts_by_status"]["verified"] == 1


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


def test_nat_cross_lane_metrics_aggregates_reports() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    report = build_nat_post_write_verification_report(runs)
    metrics = collect_nat_cross_lane_metrics([report])

    assert isinstance(metrics, NatCrossLaneMetrics)
    assert metrics.total_runs == len(runs)
    assert metrics.verified_runs == len(runs)
    assert metrics.drift_runs == 0
    assert metrics.total_claims > 0
    assert metrics.verified_claims == metrics.total_claims
    assert metrics.pending_drift_run_ids == []


def test_nat_cross_lane_metrics_reflects_pending_drifts() -> None:
    runs = _load_nat_verification_runs_fixture()["runs"]
    drift_run = copy.deepcopy(runs[0])
    drift_run["run_id"] = "run-drift"
    drift_run["batch_id"] = "batch-drift"
    drift_run["after_payload"] = {"windows": [{"id": "drift", "statement_bundles": []}]}

    report = build_nat_post_write_verification_report([drift_run], require_all_verified=True)
    metrics = collect_nat_cross_lane_metrics([report])

    assert metrics.total_runs == 1
    assert metrics.verified_runs == 0
    assert metrics.drift_runs == 1
    assert metrics.pending_drift_run_ids == ["run-drift"]
