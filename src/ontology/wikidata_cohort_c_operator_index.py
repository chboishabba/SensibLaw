from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

INDEX_SCHEMA_VERSION = "sl.wikidata_nat.cohort_c.operator_index.v0_1"


def _safe_sequence(value: Any) -> Sequence[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    if value:
        text = str(value).strip()
        return [text] if text else []
    return []


def build_nat_cohort_c_operator_index(
    evidence_packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(evidence_packet, Mapping):
        raise ValueError("Operator index requires a mapping packet")
    rows = evidence_packet.get("evidence_rows")
    if not isinstance(rows, Sequence):
        raise ValueError("Evidence packet missing evidence_rows sequence")

    qualifiers_by_ref = defaultdict(set)
    hold_reasons = defaultdict(int)
    candidate_index = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        reference_anchor = str(row.get("reference_anchor") or "").strip()
        qualifier_hint = _safe_sequence(row.get("qualifier_hint"))
        for qualifier in qualifier_hint:
            qualifiers_by_ref[reference_anchor].add(qualifier)
        hold_reason = str(row.get("operator_hold_reason") or row.get("preview_hold_reason") or "").strip()
        if hold_reason:
            hold_reasons[hold_reason] += 1
        candidate_index.append(
            {
                "qid": str(row.get("qid") or "").strip(),
                "statement_id": str(row.get("statement_id") or "").strip(),
                "reference_anchor": reference_anchor,
                "qualifier_hint": qualifier_hint,
                "hold_gate": str(row.get("hold_gate") or "review_first_population_scan"),
                "promotion_guard": str(row.get("promotion_guard") or "hold"),
            }
        )

    reference_summary = {
        ref: sorted(set(quals)) for ref, quals in qualifiers_by_ref.items() if ref
    }
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "packet_id": evidence_packet.get("packet_id"),
        "cohort_id": evidence_packet.get("cohort_id"),
        "reference_summary": reference_summary,
        "hold_reason_summary": dict(hold_reasons),
        "candidate_index": candidate_index,
        "total_candidates": len(candidate_index),
    }
