from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping, Sequence

from .wikidata_cohort_c_operator_report import (
    build_nat_cohort_c_operator_report,
)


BATCH_SCHEMA_VERSION = "sl.wikidata_nat.cohort_c.operator_report_batch.v0_1"


def _ensure_sequence(inputs: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    if not inputs:
        raise ValueError("At least one evidence packet is required for batch reporting")
    return inputs


def build_nat_cohort_c_operator_report_batch(
    event_packets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    packets = _ensure_sequence(event_packets)
    hold_reasons = Counter()
    qualifier_counts = Counter()
    references = set()
    packet_ids = []
    total_candidates = 0
    for packet in packets:
        report = build_nat_cohort_c_operator_report(packet)
        packet_ids.append(report["packet_id"])
        total_candidates += report["candidate_count"]
        hold_reasons.update(report["hold_reason_summary"])
        qualifier_counts.update(report["qualifier_counts"])
        references.update(report["reference_anchors"])
    return {
        "schema_version": BATCH_SCHEMA_VERSION,
        "packet_ids": packet_ids,
        "batch_candidate_count": total_candidates,
        "hold_reason_summary": dict(hold_reasons),
        "reference_anchors": sorted(references),
        "qualifier_counts": dict(qualifier_counts),
    }
