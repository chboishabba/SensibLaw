from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .wikidata_nat_cohort_b_operator_queue import build_nat_cohort_b_operator_queue
from .wikidata_nat_cohort_b_operator_report import build_nat_cohort_b_operator_report


WIKIDATA_NAT_COHORT_B_OPERATOR_BATCH_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_batch_report.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_case_summaries(operator_packets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, packet in enumerate(operator_packets):
        if not isinstance(packet, Mapping):
            continue
        summary = packet.get("summary", {})
        summary_map = summary if isinstance(summary, Mapping) else {}
        cases.append(
            {
                "case_id": f"cohort-b-case:{index + 1}",
                "packet_id": _stringify(packet.get("packet_id")),
                "decision": _stringify(packet.get("decision")) or "hold",
                "selected_row_count": int(summary_map.get("selected_row_count", 0) or 0),
                "variance_flag_counts": dict(summary_map.get("variance_flag_counts", {}))
                if isinstance(summary_map.get("variance_flag_counts"), Mapping)
                else {},
            }
        )
    return cases


def _packet_decision_counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(_stringify(case.get("decision")) for case in cases if _stringify(case.get("decision")))
    return {key: counts[key] for key in sorted(counts)}


def build_nat_cohort_b_operator_batch_report(
    operator_packets: Sequence[Mapping[str, Any]],
    *,
    max_queue_items: int = 100,
    max_examples: int = 10,
) -> dict[str, Any]:
    if not isinstance(operator_packets, Sequence) or isinstance(
        operator_packets, (str, bytes, bytearray)
    ):
        raise ValueError("operator_packets must be a sequence of Cohort B operator packet objects")

    case_summaries = _normalize_case_summaries(operator_packets)
    queue_payload = build_nat_cohort_b_operator_queue(
        operator_packets,
        max_queue_items=max_queue_items,
    )
    report_payload = build_nat_cohort_b_operator_report(
        queue_payload,
        max_examples=max_examples,
    )

    decision_reasons: list[str] = []
    if len(case_summaries) < 2:
        batch_status = "hold"
        decision_reasons.append("requires_at_least_two_operator_cases")
    elif queue_payload.get("queue_status") != "review_queue_ready":
        batch_status = "hold"
        decision_reasons.append("queue_not_ready")
    elif report_payload.get("report_status") != "review_only_report_ready":
        batch_status = "hold"
        decision_reasons.append("report_not_ready")
    else:
        batch_status = "batch_review_ready"
        decision_reasons.append("multi_case_operator_evidence_materialized")

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_BATCH_REPORT_SCHEMA_VERSION,
        "lane_id": _stringify(queue_payload.get("lane_id")) or "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "cohort_b_reconciled_non_business",
        "batch_status": batch_status,
        "decision_reasons": sorted(set(decision_reasons)),
        "case_summaries": case_summaries,
        "packet_decision_counts": _packet_decision_counts(case_summaries),
        "queue": queue_payload,
        "report": report_payload,
        "summary": {
            "case_count": len(case_summaries),
            "queue_item_count": int(queue_payload.get("summary", {}).get("queue_item_count", 0) or 0)
            if isinstance(queue_payload.get("summary"), Mapping)
            else 0,
            "blocked_packet_count": int(report_payload.get("summary", {}).get("blocked_packet_count", 0) or 0)
            if isinstance(report_payload.get("summary"), Mapping)
            else 0,
            "validation_error_count": int(report_payload.get("summary", {}).get("validation_error_count", 0) or 0)
            if isinstance(report_payload.get("summary"), Mapping)
            else 0,
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "non_claims": [
            "batch evidence report only",
            "not migration execution",
            "not cross-cohort arbitration",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_BATCH_REPORT_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_batch_report",
]
