from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.ontology.wikidata_nat_batch_acquisition_dispatch import (
    ACQUISITION_DISPATCH_SCHEMA_VERSION,
)
from src.ontology.wikidata_nat_batch_acquisition_plan import (
    ACQUISITION_PLAN_SCHEMA_VERSION,
)
from src.policy.carriers.canonical import canonical_sha256


FILTERED_ROUTE_REQUEST_SCHEMA_VERSION = "sl.nat_filtered_route_request.v0_1"
FILTERED_ROUTE_RECEIPT_SCHEMA_VERSION = "sl.nat_filtered_route_receipt.v0_1"
ITIR_ROUTE_BUILDER_REPO = "chboishabba/ITIR-suite"
ITIR_ROUTE_BUILDER_COMMIT = "24f62fecbec11909bcdb32916801b2315a796513"
ITIR_ROUTE_BUILDER_PATH = "tools/zelph_bin_route_builder.cpp"
ROUTE_FORMAT = "zelph-node-route/v1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _require_plan_dispatch_link(plan: Mapping[str, Any], dispatch: Mapping[str, Any]) -> None:
    if _text(plan.get("schema_version")) != ACQUISITION_PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported Nat acquisition-plan schema")
    if _text(dispatch.get("schema_version")) != ACQUISITION_DISPATCH_SCHEMA_VERSION:
        raise ValueError("unsupported Nat acquisition-dispatch schema")
    if _text(dispatch.get("source_plan_ref")) != _text(plan.get("plan_ref")):
        raise ValueError("dispatch does not derive from the supplied acquisition plan")
    if bool(dispatch.get("edits_performed")):
        raise ValueError("route request cannot derive from an editing dispatch")
    if bool(dispatch.get("consumer_verification_performed")):
        raise ValueError("route request cannot derive from a consumer-verifying dispatch")
    if bool(dispatch.get("semantic_promotion_performed")):
        raise ValueError("route request cannot derive from a promoting dispatch")


def _blocked_route_results(dispatch: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [row for row in _as_sequence(dispatch.get("results")) if isinstance(row, Mapping)]
    if not rows:
        raise ValueError("dispatch contains no result receipts")
    for row in rows:
        receipt = _as_mapping(row.get("executor_receipt"))
        if _text(row.get("execution_outcome")) != "engine_unavailable":
            raise ValueError("filtered route request requires route-blocked engine_unavailable results")
        if _text(receipt.get("transport_status")) != "blocked_missing_node_route_index":
            raise ValueError("dispatch is not blocked specifically on the node-route index")
        if bool(receipt.get("node_route_index")):
            raise ValueError("dispatch claims nodeRouteIndex is already available")
        if not bool(receipt.get("canonical_layout")):
            raise ValueError("route request requires a canonical hosted manifest")
    return rows


def _plan_tasks_by_ref(plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for task in _as_sequence(plan.get("tasks")):
        if not isinstance(task, Mapping):
            continue
        task_ref = _text(task.get("task_ref"))
        if task_ref:
            result[task_ref] = task
    return result


def build_filtered_route_request(
    plan: Mapping[str, Any],
    dispatch: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the live missing-route wall into one bounded producer request.

    QIDs are treated as exact Wikidata names, not as Zelph numeric node ids.
    The producer must first resolve each QID through the `wikidata` name surface,
    then return exact node/chunk memberships.  This function performs no route
    generation, network fetch beyond the already-recorded dispatch, edits,
    consumer verification, or semantic promotion.
    """

    _require_plan_dispatch_link(plan, dispatch)
    blocked = _blocked_route_results(dispatch)
    tasks_by_ref = _plan_tasks_by_ref(plan)

    qids: set[str] = set()
    task_refs: list[str] = []
    for result in blocked:
        task_ref = _text(result.get("task_ref"))
        task = tasks_by_ref.get(task_ref)
        if task is None:
            raise ValueError(f"dispatch references unknown plan task: {task_ref}")
        task_refs.append(task_ref)
        selector = _as_mapping(task.get("wikidata_selector_request"))
        for qid in _as_sequence(selector.get("qids")):
            text = _text(qid)
            if text:
                qids.add(text)

    if not qids:
        raise ValueError("route request contains no QIDs")

    first_receipt = _as_mapping(blocked[0].get("executor_receipt"))
    manifest_digest = _text(first_receipt.get("manifest_digest"))
    manifest_revision = _text(first_receipt.get("manifest_revision"))
    manifest_path = _text(first_receipt.get("manifest_path"))
    manifest_version = _text(first_receipt.get("manifest_version"))
    for result in blocked[1:]:
        receipt = _as_mapping(result.get("executor_receipt"))
        same = (
            _text(receipt.get("manifest_digest")) == manifest_digest
            and _text(receipt.get("manifest_revision")) == manifest_revision
            and _text(receipt.get("manifest_path")) == manifest_path
        )
        if not same:
            raise ValueError("blocked task receipts do not share one manifest identity")

    qid_list = sorted(qids)
    payload_without_ref = {
        "schema_version": FILTERED_ROUTE_REQUEST_SCHEMA_VERSION,
        "source_plan_ref": _text(plan.get("plan_ref")),
        "source_dispatch_ref": _text(dispatch.get("dispatch_ref")),
        "lane_id": _text(plan.get("lane_id")),
        "source_cohort": _text(plan.get("source_cohort")),
        "source_manifest": {
            "manifest_version": manifest_version,
            "manifest_path": manifest_path,
            "manifest_digest": manifest_digest,
            "manifest_revision": manifest_revision,
            "node_route_index_observed": False,
        },
        "producer": {
            "repository": ITIR_ROUTE_BUILDER_REPO,
            "commit": ITIR_ROUTE_BUILDER_COMMIT,
            "path": ITIR_ROUTE_BUILDER_PATH,
            "route_format": ROUTE_FORMAT,
        },
        "qid_count": len(qid_list),
        "qids": qid_list,
        "source_task_refs": sorted(task_refs),
        "qid_resolution": {
            "input_kind": "wikidata_qid_string",
            "language": "wikidata",
            "first_stage": "exact_name_to_zelph_node_id",
            "first_stage_section": "nodeOfName",
            "second_stage": "zelph_node_id_to_exact_chunk_membership",
            "second_stage_sections": ["left", "right", "nameOfNode"],
            "qid_is_not_assumed_to_equal_numeric_node_id": True,
        },
        "required_outputs": [
            "qid_to_zelph_node_ids",
            "node_to_left_chunks",
            "node_to_right_chunks",
            "node_to_name_of_node_chunks",
            "source_manifest_identity",
            "route_source_identity",
            "content_address",
        ],
        "candidate_only": True,
        "filtered_request": True,
        "full_route_materialization_required": False,
        "network_performed": False,
        "edits_performed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "source_support_paid": False,
    }
    payload = dict(payload_without_ref)
    payload["request_ref"] = "nat-filtered-route-request:" + canonical_sha256(payload_without_ref)
    return payload


def validate_filtered_route_receipt(
    request: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate producer lineage/completeness without promoting route data to source support."""

    if _text(request.get("schema_version")) != FILTERED_ROUTE_REQUEST_SCHEMA_VERSION:
        raise ValueError("unsupported filtered route-request schema")
    if _text(receipt.get("schema_version")) != FILTERED_ROUTE_RECEIPT_SCHEMA_VERSION:
        raise ValueError("unsupported filtered route-receipt schema")
    if _text(receipt.get("source_request_ref")) != _text(request.get("request_ref")):
        raise ValueError("route receipt does not derive from this request")
    if _text(receipt.get("route_format")) != ROUTE_FORMAT:
        raise ValueError("unexpected route-sidecar format")
    producer = _as_mapping(receipt.get("producer"))
    if _text(producer.get("repository")) != ITIR_ROUTE_BUILDER_REPO:
        raise ValueError("route receipt has unexpected producer repository")
    if _text(producer.get("commit")) != ITIR_ROUTE_BUILDER_COMMIT:
        raise ValueError("route receipt has unexpected producer revision")

    requested = set(_text(q) for q in _as_sequence(request.get("qids")) if _text(q))
    emitted = set(_text(q) for q in _as_sequence(receipt.get("resolved_qids")) if _text(q))
    unresolved = sorted(requested - emitted)
    validated = {
        "receipt_valid": not unresolved,
        "requested_qid_count": len(requested),
        "resolved_qid_count": len(emitted & requested),
        "unresolved_qids": unresolved,
        "route_receipt_ref": _text(receipt.get("receipt_ref")),
        "candidate_only": True,
        "source_support_paid": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
    }
    return validated


__all__ = [
    "FILTERED_ROUTE_RECEIPT_SCHEMA_VERSION",
    "FILTERED_ROUTE_REQUEST_SCHEMA_VERSION",
    "ITIR_ROUTE_BUILDER_COMMIT",
    "ITIR_ROUTE_BUILDER_PATH",
    "ITIR_ROUTE_BUILDER_REPO",
    "ROUTE_FORMAT",
    "build_filtered_route_request",
    "validate_filtered_route_receipt",
]
