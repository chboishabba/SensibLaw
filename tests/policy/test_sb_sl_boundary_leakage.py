from __future__ import annotations

from src.policy.control_evidence import (
    build_compliance_evidence_bundle,
    build_sb_to_sl_contract_payload,
    validate_sb_to_sl_contract_payload,
)
from src.policy.control_evaluator import evaluate_control_profile


def _compiled_state_artifact(*, unresolved_pressure_status: str = "none", follow_obligation=None) -> dict:
    return {
        "schema_version": "itir.normalized.artifact.v1",
        "artifact_id": "statiBaker.compiled_state:2026-04-06",
        "unresolved_pressure_status": unresolved_pressure_status,
        "follow_obligation": follow_obligation,
        "lineage": {
            "upstream_artifact_ids": [
                "statiBaker.outputs:2026-04-06:state.json",
                "log:git:2026-04-06",
            ],
        },
        "provenance_anchor": {
            "source_artifact_id": "statiBaker.outputs:2026-04-06:state.json",
            "anchor_ref": "outputs/state.json",
        },
    }


def test_build_sb_to_sl_contract_payload_extracts_allowed_wrapper_fields() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(),
        observer_overlay_refs=[{"annotation_id": "obs:1", "observer_kind": "itir_mission_graph_v1"}],
        casey_observer_refs=[{"operation_id": "op:123", "receipt_hash": "a" * 64}],
    )
    assert payload["compiled_state_id"] == "statiBaker.compiled_state:2026-04-06"
    assert payload["compiled_state_version"] == "itir.normalized.artifact.v1"
    assert payload["lineage_refs"] == [
        "statiBaker.outputs:2026-04-06:state.json",
        "log:git:2026-04-06",
    ]
    assert payload["observer_overlay_refs"][0]["annotation_id"] == "obs:1"
    assert payload["casey_observer_refs"][0]["operation_id"] == "op:123"


def test_validate_sb_to_sl_contract_payload_rejects_forbidden_semantic_or_state_fields() -> None:
    errors = validate_sb_to_sl_contract_payload(
        {
            "compiled_state_id": "statiBaker.compiled_state:2026-04-06",
            "compiled_state_version": "itir.normalized.artifact.v1",
            "unresolved_pressure_status": "none",
            "state": {"events": []},
            "summary_text": "forbidden synthetic meaning",
        }
    )
    assert any("forbidden SB->SL field: state" in error for error in errors)
    assert any("forbidden SB->SL field: summary_text" in error for error in errors)


def test_validate_sb_to_sl_contract_payload_rejects_casey_mutable_payloads() -> None:
    errors = validate_sb_to_sl_contract_payload(
        {
            "compiled_state_id": "statiBaker.compiled_state:2026-04-06",
            "compiled_state_version": "itir.normalized.artifact.v1",
            "unresolved_pressure_status": "none",
            "casey_observer_refs": [
                {
                    "operation_id": "op:123",
                    "workspace_payload": {"mutable": True},
                    "receipt_hash": "a" * 64,
                }
            ],
        }
    )
    assert any("unsupported field: workspace_payload" in error for error in errors)


def test_profile_abstains_when_only_workflow_refs_exist_without_semantic_grounding() -> None:
    payload = build_sb_to_sl_contract_payload(
        suite_normalized_artifact=_compiled_state_artifact(
            unresolved_pressure_status="follow_needed",
            follow_obligation={
                "trigger": "compiled_state_unresolved_pressure",
                "scope": "review unresolved items",
                "stop_condition": "resolve or explicitly hold",
            },
        ),
        casey_observer_refs=[{"operation_id": "op:123", "receipt_hash": "a" * 64}],
    )
    bundle = build_compliance_evidence_bundle(
        subject_ref="artifact:demo",
        subject_kind="mixed_bundle",
        sb_contract_payload=payload,
    )
    result = evaluate_control_profile(profile="iso_traceability_min", evidence_bundle=bundle)
    assert result["status"] == "insufficient_evidence"
    semantic_group = next(
        group for group in result["control_group_results"] if group["control_group_id"] == "semantic_grounding"
    )
    assert semantic_group["status"] == "insufficient_evidence"
    assert all("semantic_truth" not in row for row in result["control_group_results"])
