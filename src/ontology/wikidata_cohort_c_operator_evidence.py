from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

EVIDENCE_SCHEMA_VERSION = "sl.wikidata_nat.cohort_c.operator_evidence.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def _candidate_signature(candidate: Mapping[str, Any]) -> str:
    qid = _as_text(candidate.get("qid"))
    statement_id = _as_text(candidate.get("statement_id"))
    base = {"qid": qid, "statement_id": statement_id}
    return hashlib.sha1(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def build_nat_cohort_c_operator_evidence_packet(
    scan_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if _as_text(scan_payload.get("cohort_id")) != "non_ghg_protocol_or_missing_p459":
        raise ValueError("Cohort C operator evidence packet requires the Cohort C payload")
    sample_candidates = [
        candidate
        for candidate in scan_payload.get("sample_candidates", [])
        if isinstance(candidate, Mapping)
    ]
    evidence_rows: list[dict[str, Any]] = []
    for candidate in sorted(
        sample_candidates,
        key=lambda row: (_as_text(row.get("qid")), _as_text(row.get("statement_id"))),
    ):
        qid = _as_text(candidate.get("qid"))
        statement_id = _as_text(candidate.get("statement_id"))
        preview_hold_reason = _as_text(candidate.get("preview_hold_reason")) or _as_text(
            candidate.get("policy_note")
        )
        qualifier_hint = candidate.get("qualifier_hint") or candidate.get("qualifier_properties") or []
        if isinstance(qualifier_hint, Sequence) and not isinstance(qualifier_hint, (str, bytes)):
            qualifier_hint_list = [_as_text(entry) for entry in qualifier_hint if _as_text(entry)]
        else:
            qualifier_hint_list = []
        evidence_rows.append(
            {
                "qid": qid,
                "statement_id": statement_id,
                "label": _as_text(candidate.get("label")) or qid,
                "p459_status": _as_text(candidate.get("p459_status")),
                "preview_hold_reason": preview_hold_reason,
                "operator_hold_reason": _as_text(candidate.get("operator_hold_reason"))
                or (preview_hold_reason and f"Operator to confirm: {preview_hold_reason}")
                or "Operator confirmation required.",
                "reference_anchor": _as_text(candidate.get("reference_anchor")) or statement_id,
                "qualifier_hint": qualifier_hint_list,
                "promotion_guard": "hold",
                "hold_gate": "review_first_population_scan",
                "notes": (
                    _as_text(candidate.get("notes"))
                    or _as_text(candidate.get("policy_note"))
                ),
                "evidence_id": _candidate_signature(candidate),
            }
        )
    packet_id = hashlib.sha1(
        json.dumps(
            {
                "cohort_id": scan_payload.get("cohort_id"),
                "scan_status": scan_payload.get("scan_status"),
                "candidate_qids": [row["qid"] for row in evidence_rows],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    summary_payload = scan_payload.get("summary")
    p459_status_counts = {}
    if isinstance(summary_payload, Mapping):
        p459_status_counts = dict(summary_payload.get("p459_status_counts", {}))
    else:
        for row in evidence_rows:
            status = row["p459_status"]
            if status:
                p459_status_counts[status] = p459_status_counts.get(status, 0) + 1
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "packet_id": f"operator-evidence:{packet_id}",
        "lane_id": _as_text(scan_payload.get("lane_id")),
        "cohort_id": _as_text(scan_payload.get("cohort_id")),
        "scan_status": _as_text(scan_payload.get("scan_status")),
        "governance": {
            "automation_allowed": False,
            "fail_closed": True,
        },
        "summary": {
            "candidate_count": len(evidence_rows),
            "p459_status_counts": p459_status_counts,
            "review_first": True,
            "policy_risk": "high",
        },
        "evidence_rows": evidence_rows,
    }
