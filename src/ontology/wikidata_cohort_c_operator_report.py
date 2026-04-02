from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

REPORT_SCHEMA_VERSION = "sl.wikidata_nat.cohort_c.operator_report.v0_1"


def _extract_hold_reason(candidate: Mapping[str, Any]) -> str:
    reason = candidate.get("operator_hold_reason") or candidate.get("preview_hold_reason") or ""
    return str(reason).strip()


def build_nat_cohort_c_operator_report(
    evidence_packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(evidence_packet, Mapping):
        raise ValueError("Operator report requires a mapping evidence packet")
    evidence_rows = evidence_packet.get("evidence_rows")
    if not isinstance(evidence_rows, list):
        raise ValueError("Evidence packet missing evidence_rows list")
    hold_reasons = Counter()
    reference_anchors = []
    qualifier_hint_sets = []
    for row in evidence_rows:
        if not isinstance(row, Mapping):
            continue
        reason = _extract_hold_reason(row)
        if reason:
            hold_reasons[reason] += 1
        anchor = row.get("reference_anchor")
        if isinstance(anchor, str) and anchor.strip():
            reference_anchors.append(anchor.strip())
        qualifier_hint = row.get("qualifier_hint")
        if isinstance(qualifier_hint, list):
            qualifier_hint_sets.extend(str(entry).strip() for entry in qualifier_hint if str(entry).strip())
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "packet_id": str(evidence_packet.get("packet_id", "")),
        "lane_id": str(evidence_packet.get("lane_id", "")),
        "cohort_id": str(evidence_packet.get("cohort_id", "")),
        "hold_reason_summary": dict(hold_reasons),
        "reference_anchors": sorted(set(reference_anchors)),
        "qualifier_counts": dict(Counter(qualifier_hint_sets)),
        "candidate_count": sum(1 for row in evidence_rows if isinstance(row, Mapping)),
    }
