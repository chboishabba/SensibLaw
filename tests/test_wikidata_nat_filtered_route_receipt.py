from __future__ import annotations

from src.ontology.wikidata_nat_filtered_route_receipt import (
    NAT_FILTERED_ROUTE_RECEIPT_SCHEMA,
    validate_filtered_route_receipt,
)


def _request() -> dict:
    return {
        "schema_version": "sl.nat_filtered_route_request.v0_1",
        "request_ref": "nat-filtered-route-request:test",
        "source_dispatch_ref": "dispatch:test",
        "source_plan_ref": "plan:test",
        "qids": ["Q1", "Q2"],
        "source_manifest": {
            "manifest_version": "zelph-hf-layout/v2",
            "manifest_digest": "sha256:manifest",
            "manifest_revision": "rev",
        },
    }


def _itir_receipt() -> dict:
    return {
        "schema_version": "itir.zelph_filtered_route_receipt.v0_1",
        "source_request_ref": "nat-filtered-route-request:test",
        "source_manifest_identity": {
            "manifest_version": "zelph-hf-layout/v2",
            "manifest_digest": "sha256:manifest",
            "manifest_revision": "rev",
        },
        "producer_lineage": {
            "repository": "chboishabba/ITIR-suite",
            "derived_from": {
                "commit": "24f62fecbec11909bcdb32916801b2315a796513",
                "path": "tools/zelph_bin_route_builder.cpp",
                "route_format": "zelph-node-route/v1",
            },
            "actual_producer": {
                "commit": "actual",
                "path": "tools/zelph_bin_filtered_route_builder.cpp",
                "route_format": "zelph-filtered-route/v1",
            },
        },
        "requested_qids": ["Q1", "Q2"],
        "qid_to_zelph_node_ids": {"Q1": 10, "Q2": 20},
        "qid_to_node_of_name_chunks": {"Q1": 1, "Q2": 2},
        "node_to_left_chunks": {"10": [3], "20": [4]},
        "node_to_right_chunks": {"10": [5], "20": [6]},
        "node_to_name_of_node_chunks": {"10": [7], "20": [8]},
        "route_source_identity": {"binPath": "/tmp/wd.bin"},
        "route_artifact_content_address": "sha256:route",
        "receipt_digest_sha256": "receipt",
        "complete_qid_resolution": True,
        "unresolved_qids": [],
        "missing_node_routes": [],
        "full_route_materialization_performed": False,
        "network_performed": False,
        "source_support_paid": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
    }


def test_valid_route_receipt_closes_route_coverage_only() -> None:
    receipt = validate_filtered_route_receipt(_request(), _itir_receipt())
    assert receipt["schema_version"] == NAT_FILTERED_ROUTE_RECEIPT_SCHEMA
    assert receipt["route_coverage_verified"] is True
    assert receipt["source_support_paid"] is False
    assert receipt["consumer_verification_performed"] is False
    assert receipt["semantic_promotion_performed"] is False
    assert receipt["edits_performed"] is False
    assert receipt["next_step"] == "retry_bounded_hf_selector_with_exact_route_receipt"
    assert receipt["receipt_ref"].startswith("nat-filtered-route-receipt:")


def test_incomplete_qid_resolution_is_rejected() -> None:
    itir = _itir_receipt()
    itir["complete_qid_resolution"] = False
    itir["unresolved_qids"] = ["Q2"]
    try:
        validate_filtered_route_receipt(_request(), itir)
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("expected incomplete route receipt to fail")


def test_wrong_base_lineage_is_rejected() -> None:
    itir = _itir_receipt()
    itir["producer_lineage"]["derived_from"]["commit"] = "wrong"
    try:
        validate_filtered_route_receipt(_request(), itir)
    except ValueError as exc:
        assert "base commit" in str(exc)
    else:
        raise AssertionError("expected lineage mismatch to fail")


def test_route_receipt_cannot_claim_source_support_payment() -> None:
    itir = _itir_receipt()
    itir["source_support_paid"] = True
    try:
        validate_filtered_route_receipt(_request(), itir)
    except ValueError as exc:
        assert "source_support" in str(exc)
    else:
        raise AssertionError("expected source-support claim to fail")
