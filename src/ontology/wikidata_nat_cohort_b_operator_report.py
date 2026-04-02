from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_OPERATOR_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_report.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return sorted({_stringify(item) for item in value if _stringify(item)})


def _priority_counts(queue_items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(
        _stringify(item.get("priority")) for item in queue_items if _stringify(item.get("priority"))
    )
    return {key: counts[key] for key in sorted(counts)}


def _variance_counts(queue_items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in queue_items:
        for flag in _string_list(item.get("variance_flags", [])):
            counts[flag] += 1
    return {key: counts[key] for key in sorted(counts)}


def _top_instance_classes(queue_items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        _stringify(item.get("instance_of_qid"))
        for item in queue_items
        if _stringify(item.get("instance_of_qid"))
    )
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        {"instance_of_qid": instance_of_qid, "queue_row_count": count}
        for instance_of_qid, count in ordered
    ]


def build_nat_cohort_b_operator_report(
    queue_payload: Mapping[str, Any],
    *,
    max_examples: int = 5,
) -> dict[str, Any]:
    if not isinstance(queue_payload, Mapping):
        raise ValueError("Cohort B operator report requires queue payload object")
    if _stringify(queue_payload.get("cohort_id")) != "cohort_b_reconciled_non_business":
        raise ValueError("Cohort B operator report requires cohort_b_reconciled_non_business queue")

    queue_status = _stringify(queue_payload.get("queue_status")) or "hold"
    queue_items_raw = queue_payload.get("queue_items", [])
    if not isinstance(queue_items_raw, list):
        raise ValueError("queue payload requires queue_items list")
    queue_items = [item for item in queue_items_raw if isinstance(item, Mapping)]
    blocked_packets = [
        {"packet_id": _stringify(item.get("packet_id")), "reason": _stringify(item.get("reason"))}
        for item in queue_payload.get("blocked_packets", [])
        if isinstance(item, Mapping)
    ]
    validation_errors = [
        {
            "packet_index": _stringify(item.get("packet_index")),
            "packet_id": _stringify(item.get("packet_id")),
            "error": _stringify(item.get("error")),
        }
        for item in queue_payload.get("validation_errors", [])
        if isinstance(item, Mapping)
    ]

    if queue_status == "review_queue_ready" and queue_items:
        report_status = "review_only_report_ready"
        recommendations = [
            "Process high-priority queue rows first using bounded reviewer prompts.",
            "Keep Cohort B lane review-only; do not execute migration from this report.",
        ]
    else:
        report_status = "hold"
        queue_items = []
        recommendations = [
            "Queue is not ready; resolve blocked packets or validation errors before review scheduling.",
        ]

    examples = [
        {
            "queue_item_id": _stringify(item.get("queue_item_id")),
            "row_id": _stringify(item.get("row_id")),
            "entity_qid": _stringify(item.get("entity_qid")),
            "priority": _stringify(item.get("priority")),
            "variance_flags": _string_list(item.get("variance_flags", [])),
        }
        for item in queue_items[: max(0, max_examples)]
    ]
    queue_digest = hashlib.sha1(
        json.dumps(
            {
                "queue_status": queue_status,
                "queue_items": [_stringify(item.get("queue_item_id")) for item in queue_items],
                "blocked_packets": blocked_packets,
                "validation_errors": validation_errors,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_REPORT_SCHEMA_VERSION,
        "report_id": f"cohort-b-report:{queue_digest}",
        "lane_id": _stringify(queue_payload.get("lane_id")) or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "report_status": report_status,
        "queue_status": queue_status,
        "recommendations": recommendations,
        "examples": examples,
        "summary": {
            "queue_item_count": len(queue_items),
            "blocked_packet_count": len(blocked_packets),
            "validation_error_count": len(validation_errors),
            "priority_counts": _priority_counts(queue_items),
            "variance_flag_counts": _variance_counts(queue_items),
            "top_instance_classes": _top_instance_classes(queue_items),
            "review_first": True,
        },
        "blocked_packets": blocked_packets,
        "validation_errors": validation_errors,
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "non_claims": [
            "operator report only",
            "not migration execution",
            "not cross-cohort arbitration",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_REPORT_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_report",
]
