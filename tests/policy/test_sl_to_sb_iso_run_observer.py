from __future__ import annotations

from src.policy.sl_to_sb_observer import build_sl_to_sb_iso_run_observer_payload


def _normalized_artifact(*, unresolved_pressure_status: str = "none", follow_obligation=None) -> dict:
    return {
        "schema_version": "itir.normalized.artifact.v1",
        "artifact_role": "derived_product",
        "artifact_id": "sl.normative_policy_extract:iso-demo",
        "context_envelope_ref": {
            "envelope_id": "semantic:iso-demo",
            "envelope_kind": "normative_policy",
        },
        "provenance_anchor": {
            "source_system": "SensibLaw",
            "source_artifact_id": "semantic:iso-demo",
            "anchor_ref": "semantic_context.suite_normalized_artifact",
        },
        "lineage": {
            "upstream_artifact_ids": [
                "text:iso42001:clause-5.2",
                "fixture:iso_excerpt_pack:1",
            ]
        },
        "text_ref": {"text_id": "text:iso42001:clause-5.2"},
        "follow_obligation": follow_obligation,
        "unresolved_pressure_status": unresolved_pressure_status,
    }


def test_build_sl_to_sb_iso_run_observer_payload_is_reference_heavy() -> None:
    payload = build_sl_to_sb_iso_run_observer_payload(
        suite_normalized_artifact=_normalized_artifact(
            unresolved_pressure_status="follow_needed",
            follow_obligation={
                "trigger": "open_iso_follow_pressure",
                "scope": "bounded follow on ISO clause coverage",
                "stop_condition": "follow pressure cleared or explicitly held",
            },
        ),
        state_date="2026-04-06",
        output_refs=[
            {
                "artifact_id": "sl.ir_query_bundle:iso-demo",
                "artifact_role": "derived_product",
                "ref_kind": "ir_query_bundle",
                "ref": "outputs/ir_query_bundle.json",
            }
        ],
        casey_observer_refs=[
            {
                "workspace_id": "ws:casey:1",
                "operation_id": "op:casey:1",
                "receipt_hash": "a" * 64,
                "workspace_payload": "ignored",
            }
        ],
    )
    assert payload["observer_kind"] == "sensiblaw_iso_run_v1"
    assert payload["run_id"] == "semantic:iso-demo"
    assert payload["artifact_refs"] == [
        "semantic:iso-demo",
        "sl.normative_policy_extract:iso-demo",
    ]
    assert payload["unresolved_pressure_status"] == "follow_needed"
    assert payload["output_refs"][0]["artifact_id"] == "sl.normative_policy_extract:iso-demo"
    assert payload["output_refs"][1]["artifact_id"] == "sl.ir_query_bundle:iso-demo"
    assert payload["casey_observer_refs"][0]["operation_id"] == "op:casey:1"
    assert "workspace_payload" not in payload["casey_observer_refs"][0]
    assert "summary" not in payload


def test_build_sl_to_sb_iso_run_observer_payload_requires_state_anchor() -> None:
    try:
        build_sl_to_sb_iso_run_observer_payload(
            suite_normalized_artifact=_normalized_artifact(),
        )
    except ValueError as exc:
        assert "state_date or sb_state_id" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing state anchor to fail")
