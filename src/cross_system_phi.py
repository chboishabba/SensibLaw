from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping

SL_CROSS_SYSTEM_PHI_CONTRACT_VERSION = "sl.cross_system_phi.contract.v1"
SL_CROSS_SYSTEM_PHI_MISMATCH_WORKFLOW_VERSION = "sl.phi_mismatch_review.v1"
SL_CROSS_SYSTEM_PHI_PROVENANCE_RULE_VERSION = "sl.phi.provenance_dual_anchor.v1"


def _stable_hash(parts: Iterable[object]) -> str:
    payload = "||".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a non-empty string")
    return value.strip()


def _top_level_kind(canonical_key: str) -> str:
    return canonical_key.split(":", 1)[0].strip()


def _receipt_value(receipts: Any, kind: str) -> str | None:
    if not isinstance(receipts, list):
        return None
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        if str(receipt.get("kind") or "").strip() != kind:
            continue
        value = str(receipt.get("value") or "").strip()
        if value:
            return value
    return None


def _event_index(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    per_event = report.get("per_event", [])
    if isinstance(per_event, list):
        for row in per_event:
            if not isinstance(row, Mapping):
                continue
            event_id = str(row.get("event_id") or row.get("eventId") or "").strip()
            if event_id:
                index[event_id] = row
    text_debug = report.get("text_debug")
    if isinstance(text_debug, Mapping):
        events = text_debug.get("events")
        if isinstance(events, list):
            for row in events:
                if not isinstance(row, Mapping):
                    continue
                event_id = str(row.get("event_id") or row.get("eventId") or "").strip()
                if event_id and event_id not in index:
                    index[event_id] = row
    source_documents = report.get("source_documents")
    if isinstance(source_documents, list):
        for row in source_documents:
            if not isinstance(row, Mapping):
                continue
            event_ids = [str(value).strip() for value in row.get("eventIds", []) if isinstance(value, str) and str(value).strip()]
            text = str(row.get("text") or "")
            if not event_ids or not text:
                continue
            segments = text.split("\n\n")
            if len(segments) != len(event_ids):
                continue
            offset = 0
            for event_id, segment in zip(event_ids, segments, strict=False):
                if event_id in index:
                    offset += len(segment) + 2
                    continue
                start = offset
                end = start + len(segment)
                index[event_id] = {
                    "event_id": event_id,
                    "source_document_id": str(row.get("sourceDocumentId") or ""),
                    "source_char_start": start,
                    "source_char_end": end,
                    "text": segment,
                }
                offset = end + 2
    return index


def _event_text(event_row: Mapping[str, Any]) -> str:
    text = event_row.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raw_event = event_row.get("event")
    if isinstance(raw_event, Mapping):
        raw_text = raw_event.get("text")
        if isinstance(raw_text, str) and raw_text.strip():
            return raw_text.strip()
    raise ValueError("per_event row is missing text")


def _source_document_id(event_row: Mapping[str, Any]) -> str:
    value = event_row.get("source_document_id") or event_row.get("sourceDocumentId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("event row is missing source document id")


def _source_char_start(event_row: Mapping[str, Any]) -> int:
    value = event_row.get("source_char_start")
    if value is None:
        value = event_row.get("sourceCharStart")
    if isinstance(value, int):
        return value
    raise ValueError("event row is missing source char start")


def _source_char_end(event_row: Mapping[str, Any]) -> int:
    value = event_row.get("source_char_end")
    if value is None:
        value = event_row.get("sourceCharEnd")
    if isinstance(value, int):
        return value
    raise ValueError("event row is missing source char end")


def _build_record_ref(system_id: str, row: Mapping[str, Any]) -> str:
    event_id = _required_str(row, "event_id")
    predicate_key = _required_str(row, "predicate_key")
    subject_key = _required_str(row["subject"], "canonical_key") if isinstance(row.get("subject"), Mapping) else ""
    object_key = _required_str(row["object"], "canonical_key") if isinstance(row.get("object"), Mapping) else ""
    digest = _stable_hash((system_id, event_id, predicate_key, subject_key, object_key))[:16]
    return f"promoted://{system_id}/relation/{digest}"


def _extract_promoted_records(system_id: str, report: Mapping[str, Any]) -> list[dict[str, Any]]:
    run_id = _required_str(report, "run_id")
    event_index = _event_index(report)
    promoted_relations = report.get("promoted_relations", [])
    if not isinstance(promoted_relations, list):
        raise ValueError("report.promoted_relations must be a list")

    records: list[dict[str, Any]] = []
    for row in promoted_relations:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("canonical_promotion_status") or "").strip() != "promoted_true":
            continue
        event_id = _required_str(row, "event_id")
        event_row = event_index.get(event_id)
        if event_row is None:
            raise ValueError(f"promoted relation {event_id} is missing a per_event anchor row")
        source_document_id = _source_document_id(event_row)
        source_char_start = _source_char_start(event_row)
        source_char_end = _source_char_end(event_row)
        subject = row.get("subject")
        object_ = row.get("object")
        if not isinstance(subject, Mapping) or not isinstance(object_, Mapping):
            raise ValueError("promoted relation subject/object must be objects")
        record_ref = _build_record_ref(system_id, row)
        records.append(
            {
                "record_ref": record_ref,
                "system_id": system_id,
                "run_id": run_id,
                "event_id": event_id,
                "predicate_key": _required_str(row, "predicate_key"),
                "display_label": _required_str(row, "display_label"),
                "subject_key": _required_str(subject, "canonical_key"),
                "object_key": _required_str(object_, "canonical_key"),
                "subject_kind": _top_level_kind(_required_str(subject, "canonical_key")),
                "object_kind": _top_level_kind(_required_str(object_, "canonical_key")),
                "rule_type": _receipt_value(row.get("receipts"), "rule_type"),
                "event_text": _event_text(event_row),
                "source_document_id": source_document_id,
                "source_char_start": source_char_start,
                "source_char_end": source_char_end,
            }
        )
    if not records:
        raise ValueError(f"report for {system_id} does not contain promoted_true relations")
    return records


def _mapping_score(source: Mapping[str, Any], target: Mapping[str, Any]) -> float:
    same_shape = source["subject_kind"] == target["subject_kind"] and source["object_kind"] == target["object_kind"]
    same_rule = source.get("rule_type") == target.get("rule_type") and source.get("rule_type") is not None
    same_predicate = source["predicate_key"] == target["predicate_key"]
    if same_predicate and same_shape and same_rule:
        return 1.0
    if same_shape and same_rule:
        return 0.74
    if same_shape:
        return 0.42
    return 0.0


def _classify_mapping(source: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[str, str]:
    same_shape = source["subject_kind"] == target["subject_kind"] and source["object_kind"] == target["object_kind"]
    same_rule = source.get("rule_type") == target.get("rule_type") and source.get("rule_type") is not None
    same_predicate = source["predicate_key"] == target["predicate_key"]

    if same_predicate and same_shape and same_rule:
        return "exact", "Predicate, structural roles, and rule family align."
    if same_shape and same_rule:
        return (
            "partial",
            "Both promoted relations share rule family and actor/legal-role shape, but the predicate semantics are not equivalent.",
        )
    if same_shape:
        return (
            "incompatible",
            "The record shape aligns, but the promoted rule families differ, so transfer would overstate equivalence.",
        )
    return (
        "undefined",
        "No bounded target-system relation matches the promoted source shape in this prototype run.",
    )


def _build_provenance_rule() -> dict[str, Any]:
    return {
        "rule_id": SL_CROSS_SYSTEM_PHI_PROVENANCE_RULE_VERSION,
        "description": (
            "Every mapping and mismatch diagnostic must resolve through provenance_index to at least one "
            "anchored promoted record in each referenced system."
        ),
        "source_anchor_required": True,
        "target_anchor_required": True,
    }


def _build_mismatch_workflow() -> dict[str, Any]:
    return {
        "workflow_id": SL_CROSS_SYSTEM_PHI_MISMATCH_WORKFLOW_VERSION,
        "default_status": "open",
        "allowed_statuses": ["open", "reviewed", "waived"],
        "triage_rule": "Partial and incompatible mappings require an anchored diagnostic before downstream transfer.",
    }


def _build_provenance_index(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for record in records:
        entries.append(
            {
                "provenance_ref": record["record_ref"],
                "system_id": record["system_id"],
                "run_id": record["run_id"],
                "event_id": record["event_id"],
                "predicate_key": record["predicate_key"],
                "source_document_id": record["source_document_id"],
                "source_char_start": record["source_char_start"],
                "source_char_end": record["source_char_end"],
                "event_text": record["event_text"],
            }
        )
    return entries


def _find_best_target(source: Mapping[str, Any], targets: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    ranked = sorted(
        targets,
        key=lambda target: (
            _mapping_score(source, target),
            target["predicate_key"],
            target["record_ref"],
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    if best is None or _mapping_score(source, best) <= 0:
        return None
    return best


def build_cross_system_phi_prototype(
    *,
    motif_family: str,
    source_system_id: str,
    source_authority_scope: str,
    source_report: Mapping[str, Any],
    target_system_id: str,
    target_authority_scope: str,
    target_report: Mapping[str, Any],
) -> dict[str, Any]:
    source_records = _extract_promoted_records(source_system_id, source_report)
    target_records = _extract_promoted_records(target_system_id, target_report)
    provenance_index = _build_provenance_index([*source_records, *target_records])
    used_target_refs: set[str] = set()
    mappings: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    unresolved_mapping_ids: list[str] = []
    incompatible_mapping_ids: list[str] = []

    for index, source_record in enumerate(source_records, start=1):
        available_targets = [row for row in target_records if row["record_ref"] not in used_target_refs]
        target_record = _find_best_target(source_record, available_targets)
        status: str
        rationale: str
        mapping_id = f"phi-{index:03d}"
        provenance_refs = [source_record["record_ref"]]
        mismatch_refs: list[str] = []
        constraint_refs: list[str] = []
        target_ref: str | None = None

        if target_record is None:
            status, rationale = "undefined", (
                "No bounded target-system promoted relation matched the source record shape in this prototype."
            )
            unresolved_mapping_ids.append(mapping_id)
        else:
            used_target_refs.add(target_record["record_ref"])
            target_ref = target_record["record_ref"]
            provenance_refs.append(target_record["record_ref"])
            status, rationale = _classify_mapping(source_record, target_record)
            if status in {"partial", "incompatible"}:
                diagnostic_id = f"diag-{len(diagnostics) + 1:03d}"
                mismatch_refs.append(diagnostic_id)
                if status == "incompatible":
                    incompatible_mapping_ids.append(mapping_id)
                    constraint_refs.append("constraint://target/no_transfer_without_manual_reclassification")
                    summary = (
                        f"{source_record['predicate_key']} and {target_record['predicate_key']} share record shape "
                        "but diverge in rule family, so transfer is blocked."
                    )
                else:
                    constraint_refs.append("constraint://target/manual_scope_review_required")
                    summary = (
                        f"{source_record['predicate_key']} and {target_record['predicate_key']} are structurally close "
                        "but only partially align semantically."
                    )
                diagnostics.append(
                    {
                        "diagnostic_id": diagnostic_id,
                        "kind": "mismatch",
                        "status": "open",
                        "mapping_ids": [mapping_id],
                        "summary": summary,
                        "provenance_refs": [source_record["record_ref"], target_record["record_ref"]],
                    }
                )

        mappings.append(
            {
                "mapping_id": mapping_id,
                "source_system": source_system_id,
                "target_system": target_system_id,
                "source_ref": source_record["record_ref"],
                "target_ref": target_ref,
                "status": status,
                "compatibility_rationale": rationale,
                "provenance_refs": provenance_refs,
                **({"constraint_refs": constraint_refs} if constraint_refs else {}),
                **({"mismatch_refs": mismatch_refs} if mismatch_refs else {}),
            }
        )

    return {
        "payload_version": SL_CROSS_SYSTEM_PHI_CONTRACT_VERSION,
        "motif_family": motif_family,
        "systems": [
            {
                "system_id": source_system_id,
                "promoted_basis_ref": f"promoted://{source_system_id}/run/{_required_str(source_report, 'run_id')}",
                "authority_scope": source_authority_scope,
            },
            {
                "system_id": target_system_id,
                "promoted_basis_ref": f"promoted://{target_system_id}/run/{_required_str(target_report, 'run_id')}",
                "authority_scope": target_authority_scope,
            },
        ],
        "provenance_rule": _build_provenance_rule(),
        "provenance_index": provenance_index,
        "mappings": mappings,
        "mismatch_report": {
            "workflow": _build_mismatch_workflow(),
            "unresolved_mapping_ids": unresolved_mapping_ids,
            "incompatible_mapping_ids": incompatible_mapping_ids,
            "diagnostics": diagnostics,
        },
    }


__all__ = [
    "SL_CROSS_SYSTEM_PHI_CONTRACT_VERSION",
    "SL_CROSS_SYSTEM_PHI_MISMATCH_WORKFLOW_VERSION",
    "SL_CROSS_SYSTEM_PHI_PROVENANCE_RULE_VERSION",
    "build_cross_system_phi_prototype",
]
