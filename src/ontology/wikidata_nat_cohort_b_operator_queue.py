from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_OPERATOR_QUEUE_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_queue.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return sorted({_stringify(item) for item in value if _stringify(item)})


def _priority_for_variance_flags(flags: Sequence[str]) -> str:
    count = len([flag for flag in flags if _stringify(flag)])
    if count >= 3:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def build_nat_cohort_b_operator_queue(
    operator_packets: Sequence[Mapping[str, Any]],
    *,
    max_queue_items: int = 50,
) -> dict[str, Any]:
    if not isinstance(operator_packets, Sequence) or isinstance(
        operator_packets, (str, bytes, bytearray)
    ):
        raise ValueError("operator_packets must be a sequence of Cohort B operator packet objects")

    validation_errors: list[dict[str, str]] = []
    review_packets: list[Mapping[str, Any]] = []
    hold_packets: list[dict[str, str]] = []
    lane_id = ""
    for idx, packet in enumerate(operator_packets):
        if not isinstance(packet, Mapping):
            validation_errors.append({"packet_index": str(idx), "error": "packet_not_object"})
            continue
        packet_id = _stringify(packet.get("packet_id"))
        cohort_id = _stringify(packet.get("cohort_id"))
        decision = _stringify(packet.get("decision"))
        lane_id = lane_id or _stringify(packet.get("lane_id"))

        if cohort_id != "cohort_b_reconciled_non_business":
            validation_errors.append(
                {"packet_index": str(idx), "packet_id": packet_id, "error": "packet_not_cohort_b"}
            )
            continue
        if decision == "hold":
            hold_packets.append({"packet_id": packet_id, "reason": "packet_decision_hold"})
            continue
        if decision != "review":
            validation_errors.append(
                {
                    "packet_index": str(idx),
                    "packet_id": packet_id,
                    "error": "packet_decision_must_be_review_or_hold",
                }
            )
            continue
        selected_rows = packet.get("selected_rows")
        if not isinstance(selected_rows, list) or not selected_rows:
            validation_errors.append(
                {
                    "packet_index": str(idx),
                    "packet_id": packet_id,
                    "error": "review_packet_missing_selected_rows",
                }
            )
            continue
        review_packets.append(packet)

    queue_items: list[dict[str, Any]] = []
    for packet in review_packets:
        packet_id = _stringify(packet.get("packet_id"))
        triage_prompts = _string_list(packet.get("triage_prompts", []))
        for row in packet.get("selected_rows", []):
            if not isinstance(row, Mapping):
                continue
            variance_flags = _string_list(row.get("variance_flags", []))
            queue_items.append(
                {
                    "queue_item_id": (
                        "cohort-b-queue:"
                        + hashlib.sha1(
                            f"{packet_id}|{_stringify(row.get('row_id'))}".encode("utf-8")
                        ).hexdigest()[:12]
                    ),
                    "packet_id": packet_id,
                    "row_id": _stringify(row.get("row_id")),
                    "entity_qid": _stringify(row.get("entity_qid")),
                    "instance_of_qid": _stringify(row.get("instance_of_qid")),
                    "priority": _priority_for_variance_flags(variance_flags),
                    "variance_flags": variance_flags,
                    "triage_prompts": triage_prompts[:2],
                }
            )

    queue_items.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item["priority"], 3),
            item["packet_id"],
            item["row_id"],
        )
    )
    bounded_queue_items = queue_items[: max(0, max_queue_items)]

    if validation_errors or hold_packets:
        queue_status = "hold"
        decision_reasons = ["fail_closed_due_to_hold_or_validation_error"]
        emitted_items: list[dict[str, Any]] = []
    elif not bounded_queue_items:
        queue_status = "hold"
        decision_reasons = ["no_review_rows_available_for_queue"]
        emitted_items = []
    else:
        queue_status = "review_queue_ready"
        decision_reasons = ["validated_review_packets_materialized_to_queue"]
        emitted_items = bounded_queue_items

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_QUEUE_SCHEMA_VERSION,
        "lane_id": lane_id or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "queue_status": queue_status,
        "decision_reasons": sorted(set(decision_reasons)),
        "queue_items": emitted_items,
        "blocked_packets": hold_packets,
        "validation_errors": validation_errors,
        "summary": {
            "input_packet_count": len(operator_packets),
            "review_packet_count": len(review_packets),
            "hold_packet_count": len(hold_packets),
            "validation_error_count": len(validation_errors),
            "queue_item_count": len(emitted_items),
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "non_claims": [
            "queue materialization only",
            "not migration execution",
            "not cross-cohort arbitration",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_QUEUE_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_queue",
]
