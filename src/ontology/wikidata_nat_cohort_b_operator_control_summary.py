from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_OPERATOR_CONTROL_SUMMARY_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_control_summary.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _index_id(index_payload: Mapping[str, Any], position: int) -> str:
    digest = hashlib.sha1(
        json.dumps(
            {
                "position": position,
                "lane_id": _stringify(index_payload.get("lane_id")),
                "index_status": _stringify(index_payload.get("index_status")),
                "decision_reasons": index_payload.get("decision_reasons", []),
                "summary": index_payload.get("summary", {}),
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"cohort-b-index:{digest}"


def build_nat_cohort_b_operator_control_summary(
    index_payloads: Sequence[Mapping[str, Any]],
    *,
    min_ready_indexes: int = 2,
) -> dict[str, Any]:
    if not isinstance(index_payloads, Sequence) or isinstance(
        index_payloads, (str, bytes, bytearray)
    ):
        raise ValueError("index_payloads must be a sequence of Cohort B evidence-index objects")
    if min_ready_indexes < 1:
        raise ValueError("min_ready_indexes must be at least 1")

    entries: list[dict[str, Any]] = []
    validation_errors: list[dict[str, str]] = []
    lane_id = ""
    for idx, payload in enumerate(index_payloads):
        if not isinstance(payload, Mapping):
            validation_errors.append({"index_position": str(idx), "error": "index_not_object"})
            continue
        lane_id = lane_id or _stringify(payload.get("lane_id"))
        cohort_id = _stringify(payload.get("cohort_id"))
        index_status = _stringify(payload.get("index_status"))
        summary = payload.get("summary", {})
        summary_map = summary if isinstance(summary, Mapping) else {}
        if cohort_id != "cohort_b_reconciled_non_business":
            validation_errors.append({"index_position": str(idx), "error": "index_not_cohort_b"})
            continue
        if index_status not in {"review_index_ready", "hold"}:
            validation_errors.append({"index_position": str(idx), "error": "invalid_index_status"})
            continue
        entries.append(
            {
                "index_id": _index_id(payload, idx),
                "index_position": idx,
                "index_status": index_status,
                "decision_reasons": [
                    _stringify(item)
                    for item in payload.get("decision_reasons", [])
                    if _stringify(item)
                ]
                if isinstance(payload.get("decision_reasons"), list)
                else [],
                "ready_batch_count": int(summary_map.get("ready_batch_count", 0) or 0),
                "hold_batch_count": int(summary_map.get("hold_batch_count", 0) or 0),
                "validation_error_count": int(summary_map.get("validation_error_count", 0) or 0),
            }
        )

    entries.sort(key=lambda item: (item["index_position"], item["index_id"]))
    status_counts = Counter(entry["index_status"] for entry in entries if entry["index_status"])
    ready_entries = [entry for entry in entries if entry["index_status"] == "review_index_ready"]
    hold_entries = [entry for entry in entries if entry["index_status"] == "hold"]

    if validation_errors:
        control_status = "hold"
        decision_reasons = ["validation_errors_present"]
    elif len(ready_entries) < min_ready_indexes:
        control_status = "hold"
        decision_reasons = ["insufficient_ready_indexes"]
    elif hold_entries:
        control_status = "hold"
        decision_reasons = ["hold_indexes_present"]
    else:
        control_status = "review_control_ready"
        decision_reasons = ["ready_indexes_meet_threshold"]

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_CONTROL_SUMMARY_SCHEMA_VERSION,
        "lane_id": lane_id or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "control_status": control_status,
        "decision_reasons": decision_reasons,
        "ready_index_ids": [entry["index_id"] for entry in ready_entries]
        if control_status == "review_control_ready"
        else [],
        "index_entries": entries,
        "validation_errors": validation_errors,
        "summary": {
            "input_index_count": len(index_payloads),
            "valid_index_count": len(entries),
            "ready_index_count": len(ready_entries),
            "hold_index_count": len(hold_entries),
            "validation_error_count": len(validation_errors),
            "status_counts": _counter_dict(status_counts),
            "aggregate_ready_batch_count": sum(entry["ready_batch_count"] for entry in entries),
            "aggregate_hold_batch_count": sum(entry["hold_batch_count"] for entry in entries),
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "non_claims": [
            "operator control summary only",
            "not migration execution",
            "not cross-cohort arbitration",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_CONTROL_SUMMARY_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_control_summary",
]
