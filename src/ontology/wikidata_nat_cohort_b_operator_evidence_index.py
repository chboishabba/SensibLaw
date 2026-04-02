from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_OPERATOR_EVIDENCE_INDEX_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_evidence_index.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _batch_id(batch: Mapping[str, Any], index: int) -> str:
    payload = {
        "index": index,
        "lane_id": _stringify(batch.get("lane_id")),
        "decision_reasons": list(batch.get("decision_reasons", []))
        if isinstance(batch.get("decision_reasons"), list)
        else [],
        "packet_decision_counts": dict(batch.get("packet_decision_counts", {}))
        if isinstance(batch.get("packet_decision_counts"), Mapping)
        else {},
        "summary": dict(batch.get("summary", {})) if isinstance(batch.get("summary"), Mapping) else {},
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    return f"cohort-b-batch:{digest}"


def build_nat_cohort_b_operator_evidence_index(
    batch_reports: Sequence[Mapping[str, Any]],
    *,
    min_ready_batches: int = 2,
) -> dict[str, Any]:
    if not isinstance(batch_reports, Sequence) or isinstance(
        batch_reports, (str, bytes, bytearray)
    ):
        raise ValueError("batch_reports must be a sequence of Cohort B batch-report objects")
    if min_ready_batches < 1:
        raise ValueError("min_ready_batches must be at least 1")

    validation_errors: list[dict[str, str]] = []
    batch_entries: list[dict[str, Any]] = []
    lane_id = ""

    for index, batch in enumerate(batch_reports):
        if not isinstance(batch, Mapping):
            validation_errors.append({"batch_index": str(index), "error": "batch_not_object"})
            continue
        lane_id = lane_id or _stringify(batch.get("lane_id"))
        cohort_id = _stringify(batch.get("cohort_id"))
        batch_status = _stringify(batch.get("batch_status"))
        summary = batch.get("summary", {})
        summary_map = summary if isinstance(summary, Mapping) else {}
        if cohort_id != "cohort_b_reconciled_non_business":
            validation_errors.append(
                {"batch_index": str(index), "error": "batch_not_cohort_b"}
            )
            continue
        if batch_status not in {"batch_review_ready", "hold"}:
            validation_errors.append(
                {"batch_index": str(index), "error": "invalid_batch_status"}
            )
            continue
        batch_entries.append(
            {
                "batch_id": _batch_id(batch, index),
                "batch_index": index,
                "batch_status": batch_status,
                "decision_reasons": [
                    _stringify(item)
                    for item in batch.get("decision_reasons", [])
                    if _stringify(item)
                ]
                if isinstance(batch.get("decision_reasons"), list)
                else [],
                "case_count": int(summary_map.get("case_count", 0) or 0),
                "queue_item_count": int(summary_map.get("queue_item_count", 0) or 0),
                "blocked_packet_count": int(summary_map.get("blocked_packet_count", 0) or 0),
                "validation_error_count": int(summary_map.get("validation_error_count", 0) or 0),
            }
        )

    batch_entries.sort(key=lambda item: (item["batch_index"], item["batch_id"]))

    status_counts = Counter(entry["batch_status"] for entry in batch_entries if entry["batch_status"])
    ready_batches = [entry for entry in batch_entries if entry["batch_status"] == "batch_review_ready"]
    hold_batches = [entry for entry in batch_entries if entry["batch_status"] == "hold"]

    if validation_errors:
        index_status = "hold"
        decision_reasons = ["validation_errors_present"]
    elif len(ready_batches) < min_ready_batches:
        index_status = "hold"
        decision_reasons = ["insufficient_ready_batches"]
    elif hold_batches:
        index_status = "hold"
        decision_reasons = ["hold_batches_present"]
    else:
        index_status = "review_index_ready"
        decision_reasons = ["ready_batches_meet_threshold"]

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_EVIDENCE_INDEX_SCHEMA_VERSION,
        "lane_id": lane_id or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "index_status": index_status,
        "decision_reasons": decision_reasons,
        "ready_batch_ids": [entry["batch_id"] for entry in ready_batches]
        if index_status == "review_index_ready"
        else [],
        "batch_entries": batch_entries,
        "validation_errors": validation_errors,
        "summary": {
            "input_batch_count": len(batch_reports),
            "valid_batch_count": len(batch_entries),
            "ready_batch_count": len(ready_batches),
            "hold_batch_count": len(hold_batches),
            "validation_error_count": len(validation_errors),
            "status_counts": _counter_dict(status_counts),
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "non_claims": [
            "operator evidence index only",
            "not migration execution",
            "not cross-cohort arbitration",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_EVIDENCE_INDEX_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_evidence_index",
]
