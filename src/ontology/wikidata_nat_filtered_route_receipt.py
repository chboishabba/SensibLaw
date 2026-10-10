from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


FILTERED_ROUTE_REQUEST_SCHEMA = "sl.nat_filtered_route_request.v0_1"
ITIR_FILTERED_ROUTE_RECEIPT_SCHEMA = "itir.zelph_filtered_route_receipt.v0_1"
NAT_FILTERED_ROUTE_RECEIPT_SCHEMA = "sl.nat_filtered_route_receipt.v0_1"
PINNED_BASE_PRODUCER_COMMIT = "24f62fecbec11909bcdb32916801b2315a796513"
PINNED_BASE_PRODUCER_PATH = "tools/zelph_bin_route_builder.cpp"
EXPECTED_FILTERED_PRODUCER_PATH = "tools/zelph_bin_filtered_route_builder.cpp"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return sorted({_text(item) for item in value if _text(item)})


def validate_filtered_route_receipt(
    request: Mapping[str, Any],
    itir_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind an ITIR filtered-route receipt to the exact Nat request.

    This validates route provenance/coverage only.  A valid route receipt does not
    pay source_support and does not perform external-reference or consumer
    verification.
    """

    if _text(request.get("schema_version")) != FILTERED_ROUTE_REQUEST_SCHEMA:
        raise ValueError("unsupported Nat filtered-route request schema")
    if _text(itir_receipt.get("schema_version")) != ITIR_FILTERED_ROUTE_RECEIPT_SCHEMA:
        raise ValueError("unsupported ITIR filtered-route receipt schema")
    if _text(itir_receipt.get("source_request_ref")) != _text(request.get("request_ref")):
        raise ValueError("ITIR receipt does not bind the exact Nat route request")

    requested_qids = _text_list(request.get("qids"))
    receipt_qids = _text_list(itir_receipt.get("requested_qids"))
    if requested_qids != receipt_qids:
        raise ValueError("ITIR receipt QID set differs from Nat request")

    lineage = _mapping(itir_receipt.get("producer_lineage"))
    derived_from = _mapping(lineage.get("derived_from"))
    actual_producer = _mapping(lineage.get("actual_producer"))
    if _text(derived_from.get("commit")) != PINNED_BASE_PRODUCER_COMMIT:
        raise ValueError("filtered route receipt lost pinned ITIR base commit lineage")
    if _text(derived_from.get("path")) != PINNED_BASE_PRODUCER_PATH:
        raise ValueError("filtered route receipt lost pinned ITIR base producer path")
    if _text(actual_producer.get("path")) != EXPECTED_FILTERED_PRODUCER_PATH:
        raise ValueError("unexpected filtered route executable path")
    actual_commit = _text(actual_producer.get("commit"))
    if not actual_commit:
        raise ValueError("filtered route receipt missing actual producer commit")

    expected_manifest = _mapping(request.get("source_manifest"))
    observed_manifest = _mapping(itir_receipt.get("source_manifest_identity"))
    for field in ("manifest_version", "manifest_digest", "manifest_revision"):
        if _text(observed_manifest.get(field)) != _text(expected_manifest.get(field)):
            raise ValueError(f"filtered route receipt manifest mismatch: {field}")

    qid_to_node = _mapping(itir_receipt.get("qid_to_zelph_node_ids"))
    unresolved = _text_list(itir_receipt.get("unresolved_qids"))
    missing_routes = _text_list(itir_receipt.get("missing_node_routes"))
    if not bool(itir_receipt.get("complete_qid_resolution")):
        raise ValueError("filtered route receipt is incomplete")
    if unresolved or missing_routes:
        raise ValueError("filtered route receipt retains unresolved route residuals")
    for qid in requested_qids:
        if qid not in qid_to_node or qid_to_node[qid] is None:
            raise ValueError(f"filtered route receipt missing node id for {qid}")

    required_maps = {
        "node_to_left_chunks": _mapping(itir_receipt.get("node_to_left_chunks")),
        "node_to_right_chunks": _mapping(itir_receipt.get("node_to_right_chunks")),
        "node_to_name_of_node_chunks": _mapping(itir_receipt.get("node_to_name_of_node_chunks")),
    }
    node_ids = sorted({_text(qid_to_node[qid]) for qid in requested_qids})
    for name, mapping in required_maps.items():
        for node in node_ids:
            if node not in mapping:
                raise ValueError(f"filtered route receipt missing {name} entry for node {node}")

    route_content_address = _text(itir_receipt.get("route_artifact_content_address"))
    if not route_content_address.startswith("sha256:"):
        raise ValueError("filtered route artifact lacks SHA-256 content address")

    if bool(itir_receipt.get("full_route_materialization_performed")):
        raise ValueError("bounded Nat receipt refuses full-route materialization")
    if bool(itir_receipt.get("source_support_paid")):
        raise ValueError("route producer cannot pay source_support")
    if bool(itir_receipt.get("consumer_verification_performed")):
        raise ValueError("route producer cannot perform Nat consumer verification")
    if bool(itir_receipt.get("semantic_promotion_performed")):
        raise ValueError("route producer cannot perform semantic promotion")
    if bool(itir_receipt.get("edits_performed")):
        raise ValueError("route producer cannot perform edits")

    payload_without_ref = {
        "schema_version": NAT_FILTERED_ROUTE_RECEIPT_SCHEMA,
        "source_request_ref": _text(request.get("request_ref")),
        "source_dispatch_ref": _text(request.get("source_dispatch_ref")),
        "source_plan_ref": _text(request.get("source_plan_ref")),
        "source_manifest_identity": dict(observed_manifest),
        "producer_lineage": dict(lineage),
        "requested_qids": requested_qids,
        "qid_to_zelph_node_ids": dict(qid_to_node),
        "qid_to_node_of_name_chunks": dict(_mapping(itir_receipt.get("qid_to_node_of_name_chunks"))),
        "node_to_left_chunks": dict(required_maps["node_to_left_chunks"]),
        "node_to_right_chunks": dict(required_maps["node_to_right_chunks"]),
        "node_to_name_of_node_chunks": dict(required_maps["node_to_name_of_node_chunks"]),
        "route_source_identity": dict(_mapping(itir_receipt.get("route_source_identity"))),
        "route_artifact_content_address": route_content_address,
        "itir_receipt_digest_sha256": _text(itir_receipt.get("receipt_digest_sha256")),
        "route_coverage_verified": True,
        "network_performed": bool(itir_receipt.get("network_performed", False)),
        "source_support_paid": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "edits_performed": False,
        "next_step": "retry_bounded_hf_selector_with_exact_route_receipt",
    }
    payload = dict(payload_without_ref)
    payload["receipt_ref"] = "nat-filtered-route-receipt:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = [
    "FILTERED_ROUTE_REQUEST_SCHEMA",
    "ITIR_FILTERED_ROUTE_RECEIPT_SCHEMA",
    "NAT_FILTERED_ROUTE_RECEIPT_SCHEMA",
    "validate_filtered_route_receipt",
]
