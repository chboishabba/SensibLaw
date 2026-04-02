from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_b_operator_packet.v0_1"
)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return sorted({_stringify(item) for item in value if _stringify(item)})


def _normalize_review_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("review_bucket_rows", [])
    if not isinstance(rows, list):
        raise ValueError("review bucket payload requires review_bucket_rows list")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("review bucket rows must be objects")
        variance_flags = _string_list(row.get("variance_flags", []))
        normalized.append(
            {
                "row_id": _stringify(row.get("row_id")),
                "entity_qid": _stringify(row.get("entity_qid")),
                "instance_of_qid": _stringify(row.get("instance_of_qid")),
                "variance_flags": variance_flags,
                "reviewer_questions": _string_list(row.get("reviewer_questions", [])),
            }
        )
    normalized.sort(
        key=lambda item: (-len(item["variance_flags"]), item["instance_of_qid"], item["row_id"])
    )
    return normalized


def _variance_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for flag in row.get("variance_flags", []):
            key = _stringify(flag)
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _triage_prompts(*, decision: str, counts: Mapping[str, int], violations: Sequence[Mapping[str, Any]]) -> list[str]:
    if decision == "hold":
        if violations:
            return [
                "Payload violated the Cohort B contract; remove out-of-lane rows and retry.",
                "Do not produce operator review packets for rows with unreconciled or business-family instance-of classes.",
            ]
        return [
            "No valid Cohort B rows were available; hold and refresh bounded candidate materialization.",
        ]

    prompts = [
        "Review highest-variance Cohort B rows first; keep lane review-only.",
        "Confirm class-local semantics before any migration-equivalence judgment.",
    ]
    if counts.get("unexpected_qualifier_properties", 0) > 0:
        prompts.append("Inspect unexpected qualifier properties as potential class-specific semantics.")
    if counts.get("unexpected_reference_properties", 0) > 0:
        prompts.append("Inspect unexpected reference properties for citation-shape drift.")
    if counts.get("mixed_temporal_qualifier_resolution", 0) > 0:
        prompts.append("Resolve temporal qualifier-mode mixing before downstream decisions.")
    return prompts


def build_nat_cohort_b_operator_packet(
    review_bucket_payload: Mapping[str, Any],
    *,
    max_rows: int = 5,
) -> dict[str, Any]:
    if not isinstance(review_bucket_payload, Mapping):
        raise ValueError("Cohort B operator packet requires review bucket payload object")
    if _stringify(review_bucket_payload.get("cohort_id")) != "cohort_b_reconciled_non_business":
        raise ValueError("Cohort B operator packet requires cohort_b_reconciled_non_business payload")

    source_decision = _stringify(review_bucket_payload.get("decision")) or "hold"
    if source_decision not in {"review_only", "hold"}:
        raise ValueError("review bucket decision must be review_only or hold")

    violations = [
        {"row_id": _stringify(item.get("row_id")), "violation": _stringify(item.get("violation"))}
        for item in review_bucket_payload.get("contract_violations", [])
        if isinstance(item, Mapping)
    ]
    rows = _normalize_review_rows(review_bucket_payload)
    if source_decision == "hold" and rows:
        raise ValueError("hold review bucket payload must not contain review rows")

    packet_decision = "review" if source_decision == "review_only" and rows else "hold"
    if packet_decision == "hold":
        selected_rows: list[dict[str, Any]] = []
    else:
        selected_rows = rows[: max(0, max_rows)]

    counts = _variance_counts(selected_rows if selected_rows else rows)
    packet_id = hashlib.sha1(
        json.dumps(
            {
                "lane_id": _stringify(review_bucket_payload.get("lane_id")),
                "cohort_id": "cohort_b_reconciled_non_business",
                "packet_decision": packet_decision,
                "row_ids": [row["row_id"] for row in selected_rows],
                "violation_keys": [item["violation"] for item in violations],
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "schema_version": WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION,
        "packet_id": f"operator-packet:{packet_id}",
        "lane_id": _stringify(review_bucket_payload.get("lane_id")),
        "cohort_id": "cohort_b_reconciled_non_business",
        "decision": packet_decision,
        "source_bucket_decision": source_decision,
        "triage_prompts": _triage_prompts(
            decision=packet_decision,
            counts=counts,
            violations=violations,
        ),
        "selected_rows": selected_rows,
        "summary": {
            "selected_row_count": len(selected_rows),
            "source_review_row_count": len(rows),
            "contract_violation_count": len(violations),
            "variance_flag_counts": counts,
            "review_first": True,
        },
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
            "requires_human_review": True,
        },
        "contract_violations": violations,
        "non_claims": [
            "operator review packet only",
            "not migration execution",
            "not cross-cohort routing",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_B_OPERATOR_PACKET_SCHEMA_VERSION",
    "build_nat_cohort_b_operator_packet",
]
