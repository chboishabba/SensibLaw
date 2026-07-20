from __future__ import annotations

import inspect

from sensiblaw import (
    attach_receipt,
    build_input_envelope,
    build_world_model,
    project_linkage_case,
    project_report,
)
from src.ontology import nat
from src.policy import brexit
from src.policy.adapter_discovery import UnsupportedInputError
from src.policy.au_world_model import AU_FACT_REVIEW_BUNDLE_FAMILY_ID
from src.policy.linkage_depth import LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION


def test_public_api_exports_generic_world_model_surface() -> None:
    world_model = build_world_model("Example text for bounded review.")
    report = project_report(world_model)

    assert world_model["lane_family"] == "generic_input"
    assert report["schema_version"] == "sl.generic_world_model_report.v0_1"
    assert "linkage_case" in report


def test_public_api_auto_detects_au_review_bundle_mapping() -> None:
    bundle = {
        "version": "fact.review.bundle.v1",
        "run": {"fact_run_id": "fact-run-1", "semantic_run_id": "semantic-run-1"},
        "review_queue": [
            {
                "fact_id": "fact:1",
                "label": "Candidate AU fact",
                "candidate_status": "candidate_only",
                "reason_codes": ["authority_gap"],
                "policy_outcomes": ["review"],
                "event_ids": ["event:1"],
            }
        ],
        "compiler_contract": {},
        "promotion_gate": {},
        "workflow_summary": {},
        "operator_workflow_surface": {},
    }

    world_model = build_world_model(bundle)

    assert world_model["lane_family"] == AU_FACT_REVIEW_BUNDLE_FAMILY_ID
    assert world_model["metadata"]["runtime_adapter"] == "au_review_bundle"


def test_public_api_auto_detects_brexit_record_rows() -> None:
    records = brexit.load_records()

    world_model = build_world_model(records)

    assert world_model["metadata"]["runtime_adapter"] == "brexit_records"
    assert world_model["summary"]["claim_count"] >= 1


def test_public_api_supports_nat_profile_via_schema_marker() -> None:
    """NAT profiles are discovered via schema_version marker, not compat metadata."""
    payload = {
        "schema_version": "sl.nat_wikidata_profile.v0_1",
        "profile_id": "climate_review_demonstrator",
    }

    world_model = build_world_model(payload)

    assert world_model["metadata"]["runtime_adapter"] == "nat:climate_review_demonstrator"


def test_generic_attach_receipt_accepts_linkage_projection_only() -> None:
    world_model = build_world_model("Example text for receipt projection.")
    linkage_case = project_linkage_case(world_model)
    wrapped = attach_receipt(linkage_case)

    assert wrapped["linkage_depth_receipt"]["schema_version"] == LINKAGE_DEPTH_RECEIPT_SCHEMA_VERSION


def test_nat_and_brexit_wrappers_match_generic_projection_path() -> None:
    nat_report = nat.build_report("climate_review_demonstrator")
    nat_generic = project_report(
        build_world_model(
            {
                "schema_version": "sl.nat_wikidata_profile.v0_1",
                "profile_id": "climate_review_demonstrator",
            },
        )
    )
    brexit_records = brexit.load_records()
    brexit_report = brexit.build_report(brexit_records)
    brexit_generic = project_report(build_world_model(brexit_records))

    assert nat_report["artifact_id"] == nat_generic["artifact_id"]
    assert nat_report["linkage_case"]["payload"]["case_id"] == nat_generic["linkage_case"]["payload"]["case_id"]
    assert brexit_report["artifact_id"] == brexit_generic["artifact_id"]
    assert brexit_report["linkage_case"]["payload"]["case_id"] == brexit_generic["linkage_case"]["payload"]["case_id"]


def test_public_api_rejects_lane_shaped_adapter_hints() -> None:
    assert "adapter_hint" not in inspect.signature(build_input_envelope).parameters

    try:
        build_world_model(
            {},
            envelope={
                "schema_version": "sl.world_model_input_envelope.v0_1",
                "input_id": "legacy",
                "input_kind": "mapping",
                "adapter_hint": "nat_profile",
                "payload": {},
                "metadata": {},
            },
        )
    except ValueError as exc:
        assert "adapter_hint is not part of the public world-model input boundary" in str(exc)
    else:
        raise AssertionError("expected build_world_model to reject adapter_hint")


def test_public_api_rejects_smuggled_compat_metadata() -> None:
    """Smuggled _compat_family / _compat_profile / _artifact_shape are rejected."""
    for key in ("_compat_family", "_compat_profile", "_artifact_shape"):
        try:
            build_world_model(
                {},
                envelope={
                    "schema_version": "sl.world_model_input_envelope.v0_1",
                    "input_id": "test",
                    "input_kind": "mapping",
                    "payload": {},
                    "metadata": {key: "smuggled_value"},
                },
            )
        except ValueError as exc:
            assert "not part of the public world-model input boundary" in str(exc)
        else:
            raise AssertionError(f"expected build_world_model to reject {key}")


def test_build_world_model_has_no_adapter_selector_parameter() -> None:
    """build_world_model() accepts data, not adapter names."""
    sig = inspect.signature(build_world_model)
    forbidden = {"adapter_hint", "profile", "kind", "lane", "adapter"}
    intersection = forbidden & set(sig.parameters)
    assert not intersection, f"build_world_model has forbidden parameters: {intersection}"
