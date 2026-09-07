from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.ontology.wikidata_nat_batch_prerequisite_runner import BATCH_RESULT_SCHEMA_VERSION


ACQUISITION_PLAN_SCHEMA_VERSION = "sl.nat_batch_acquisition_plan.v0_1"
ACQUISITION_TASK_SCHEMA_VERSION = "sl.nat_batch_acquisition_task.v0_1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _text_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return sorted({_text(value) for value in values if _text(value)})


def _require_dry_batch(batch: Mapping[str, Any]) -> None:
    if _text(batch.get("schema_version")) != BATCH_RESULT_SCHEMA_VERSION:
        raise ValueError("unsupported Nat batch prerequisite schema")
    if _text(batch.get("mode")) != "dry_classification_only":
        raise ValueError("acquisition planning requires a dry-classification batch")
    forbidden_true = (
        "network_performed",
        "edits_performed",
        "consumer_verification_performed",
        "semantic_promotion_performed",
    )
    if any(bool(batch.get(field)) for field in forbidden_true):
        raise ValueError("dry batch already claims side effects or semantic promotion")


def _rows_by_ref(batch: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = batch.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_ref = _text(row.get("row_ref"))
        if row_ref:
            result[row_ref] = row
    return result


def _external_reference_obligations(reference_properties: Sequence[str]) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    for property_id in sorted(set(reference_properties)):
        if property_id == "P854":
            obligations.append(
                {
                    "reference_property": "P854",
                    "obligation": "fetch_and_verify_external_reference_url_content",
                    "mechanism": "external_source_acquisition",
                    "candidate_only": True,
                }
            )
        elif property_id == "P248":
            obligations.append(
                {
                    "reference_property": "P248",
                    "obligation": "resolve_and_verify_stated_in_source",
                    "mechanism": "external_source_acquisition",
                    "candidate_only": True,
                }
            )
        elif property_id == "P143":
            obligations.append(
                {
                    "reference_property": "P143",
                    "obligation": "preserve_imported_from_provenance_only",
                    "mechanism": "provenance_preservation",
                    "candidate_only": True,
                }
            )
        else:
            obligations.append(
                {
                    "reference_property": property_id,
                    "obligation": "review_reference_role",
                    "mechanism": "review",
                    "candidate_only": True,
                }
            )
    return obligations


def _build_task(
    group: Mapping[str, Any],
    rows_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    signature = group.get("signature")
    if not isinstance(signature, Mapping):
        raise ValueError("work group missing signature")
    if _text(signature.get("first_missing_prerequisite")) != "source_support":
        raise ValueError("phase-two planner currently accepts source-support groups only")
    if _text(signature.get("mechanism")) != "look":
        raise ValueError("source-support acquisition must remain a Look mechanism")
    if _text(signature.get("selector_class")) != "zelph_hf_selector":
        raise ValueError("phase-two planner currently accepts Zelph/HF groups only")

    member_refs = _text_list(group.get("member_row_refs"))
    members: list[Mapping[str, Any]] = []
    for row_ref in member_refs:
        row = rows_by_ref.get(row_ref)
        if row is None:
            raise ValueError(f"work group references unknown row: {row_ref}")
        members.append(row)

    qids = sorted({_text(row.get("qid")) for row in members if _text(row.get("qid"))})
    statement_refs = sorted(
        {
            _text(row.get("statement_reference"))
            for row in members
            if _text(row.get("statement_reference"))
        }
    )
    qualifier_properties = _text_list(signature.get("qualifier_properties"))
    reference_properties = _text_list(signature.get("reference_properties"))
    source_property = _text(signature.get("source_property"))
    target_property = _text(signature.get("target_property"))

    task_without_ref = {
        "schema_version": ACQUISITION_TASK_SCHEMA_VERSION,
        "source_group_ref": _text(group.get("group_ref")),
        "source_signature_ref": _text(signature.get("signature_ref")),
        "target_prerequisite": "source_support",
        "required_producer": "acquire_source_support",
        "mechanism": "look",
        "selector_class": "zelph_hf_selector",
        "member_count": len(members),
        "member_row_refs": member_refs,
        "qids": qids,
        "statement_references": statement_refs,
        "source_property": source_property,
        "target_property": target_property,
        "qualifier_properties": qualifier_properties,
        "reference_properties": reference_properties,
        "wikidata_selector_request": {
            "operations": [
                "node_route_selection",
                "sparql_subset",
                "partial_loading",
                "qualifier_reference_import",
            ],
            "qids": qids,
            "properties": sorted(
                set(
                    [source_property, target_property]
                    + qualifier_properties
                    + reference_properties
                )
            ),
            "required_outputs": [
                "statement_snapshot",
                "qualifier_snaks",
                "reference_snaks",
                "source_revision_lineage",
                "content_address",
            ],
            "full_reasoning_required": False,
            "candidate_only": True,
        },
        "external_reference_obligations": _external_reference_obligations(
            reference_properties
        ),
        "payment_policy": {
            "wikidata_selector_output_alone_pays_source_support": False,
            "external_reference_presence_alone_pays_source_support": False,
            "consumer_verification_required": True,
            "semantic_promotion_allowed": False,
            "edit_authority": False,
        },
        "dispatch_status": "planned_not_dispatched",
    }
    task = dict(task_without_ref)
    task["task_ref"] = "nat-acquisition-task:" + canonical_sha256(task_without_ref)
    return task


def build_acquisition_plan(batch: Mapping[str, Any]) -> dict[str, Any]:
    """Compile a dry Nat prerequisite batch into bounded acquisition tasks.

    This function performs no network requests or edits.  It only plans bounded
    selector work for source-support groups and preserves the distinction between
    retrieving Wikidata reference metadata and verifying the external source named
    by that metadata.
    """

    _require_dry_batch(batch)
    rows_by_ref = _rows_by_ref(batch)
    groups = batch.get("work_groups")
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes, bytearray)):
        groups = []

    tasks = [
        _build_task(group, rows_by_ref)
        for group in groups
        if isinstance(group, Mapping)
    ]
    tasks.sort(key=lambda task: _text(task.get("task_ref")))

    task_counts = Counter(_text(task.get("target_prerequisite")) for task in tasks)
    payload_without_ref = {
        "schema_version": ACQUISITION_PLAN_SCHEMA_VERSION,
        "source_batch_ref": _text(batch.get("batch_ref")),
        "lane_id": _text(batch.get("lane_id")),
        "source_cohort": _text(batch.get("source_cohort")),
        "source_population": batch.get("source_population"),
        "materialized_row_count": batch.get("materialized_row_count"),
        "source_work_group_count": batch.get("work_group_count"),
        "planned_task_count": len(tasks),
        "planned_member_count": sum(int(task.get("member_count", 0) or 0) for task in tasks),
        "counts_by_target_prerequisite": dict(sorted(task_counts.items())),
        "tasks": tasks,
        "network_performed": False,
        "edits_performed": False,
        "consumer_verification_performed": False,
        "semantic_promotion_performed": False,
        "formal_contract_reference": _text(batch.get("formal_contract_reference")),
    }
    payload = dict(payload_without_ref)
    payload["plan_ref"] = "nat-acquisition-plan:" + canonical_sha256(payload_without_ref)
    return payload


__all__ = [
    "ACQUISITION_PLAN_SCHEMA_VERSION",
    "ACQUISITION_TASK_SCHEMA_VERSION",
    "build_acquisition_plan",
]
