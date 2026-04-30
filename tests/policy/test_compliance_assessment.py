from __future__ import annotations

from src.policy.compliance_assessment import build_compliance_assessment
from src.policy.control_evidence import (
    build_compliance_evidence_bundle,
    build_sb_to_sl_contract_payload,
)


def _compiled_state_artifact(
    *,
    unresolved_pressure_status: str = "none",
    follow_obligation=None,
    legal_follow_pressure=None,
) -> dict:
    return {
        "schema_version": "itir.normalized.artifact.v1",
        "artifact_id": "statiBaker.compiled_state:2026-04-06",
        "unresolved_pressure_status": unresolved_pressure_status,
        "follow_obligation": follow_obligation,
        "legal_follow_pressure": legal_follow_pressure,
        "lineage": {
            "upstream_artifact_ids": [
                "statiBaker.outputs:2026-04-06:state.json",
                "sl.iso_run:demo",
            ],
        },
        "provenance_anchor": {
            "source_artifact_id": "statiBaker.outputs:2026-04-06:state.json",
            "anchor_ref": "outputs/state.json",
        },
    }


def test_compliance_assessment_succeeds_with_grouped_clause_evidence() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(),
        casey_observer_refs=[{"build_id": "build:123", "receipt_hash": "a" * 64}],
    )
    bundle = build_compliance_evidence_bundle(
        subject_ref="artifact:iso-demo",
        subject_kind="sl_artifact",
        sb_contract_payload=payload,
        semantic_evidence_refs=["text:iso42001:clause-5.2", "policy_statement:1"],
        native_artifact_refs=["sl.normative_policy_extract:demo"],
    )
    assessment = build_compliance_assessment(
        profile="iso_traceability_min",
        evidence_bundle=bundle,
    )
    assert assessment["status"] == "satisfied"
    assert assessment["summary"]["group_count"] == 3
    assert assessment["summary"]["satisfied_count"] == 3


def test_compliance_assessment_marks_missing_follow_obligation_as_not_satisfied() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(unresolved_pressure_status="follow_needed"),
    )
    bundle = build_compliance_evidence_bundle(
        subject_ref="artifact:iso-demo",
        subject_kind="sb_compiled_state",
        sb_contract_payload=payload,
        semantic_evidence_refs=["review_text:1"],
    )
    assessment = build_compliance_assessment(
        profile="iso_traceability_min",
        evidence_bundle=bundle,
    )
    workflow_group = next(
        row for row in assessment["control_group_results"] if row["control_group_id"] == "workflow_traceability"
    )
    assert workflow_group["status"] == "not_satisfied"
    assert assessment["status"] == "not_satisfied"


def test_compliance_assessment_keeps_legal_follow_pressure_additive_to_unresolved_pressure() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(
            unresolved_pressure_status="none",
            legal_follow_pressure={
                "kind": "pressure_lattice",
                "version": "sl.legal_follow_pressure.v1",
                "value": "high",
            },
        ),
    )
    bundle = build_compliance_evidence_bundle(
        subject_ref="artifact:iso-demo",
        subject_kind="sb_compiled_state",
        sb_contract_payload=payload,
        semantic_evidence_refs=["review_text:1"],
    )
    assessment = build_compliance_assessment(
        profile="iso_traceability_min",
        evidence_bundle=bundle,
    )
    workflow_group = next(
        row for row in assessment["control_group_results"] if row["control_group_id"] == "workflow_traceability"
    )
    clause = next(
        row for row in workflow_group["member_clause_results"] if row["clause_id"] == "follow_pressure_visibility"
    )
    assert clause["status"] == "satisfied"
    assert "unresolved_pressure_status:none" in clause["evidence_refs"]
    assert "legal_follow_pressure.value:high" in clause["evidence_refs"]


def test_compliance_assessment_marks_casey_group_not_applicable_without_casey_refs() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(),
    )
    bundle = build_compliance_evidence_bundle(
        subject_ref="artifact:iso-demo",
        subject_kind="sb_compiled_state",
        sb_contract_payload=payload,
        semantic_evidence_refs=["review_text:1"],
    )
    assessment = build_compliance_assessment(
        profile="iso_traceability_min",
        evidence_bundle=bundle,
    )
    execution_group = next(
        row for row in assessment["control_group_results"] if row["control_group_id"] == "execution_traceability"
    )
    assert execution_group["status"] == "not_applicable"
