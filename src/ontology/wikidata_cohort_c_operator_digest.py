from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from .wikidata_cohort_c_operator_index import build_nat_cohort_c_operator_index

DIGEST_SCHEMA_VERSION = "sl.wikidata_nat.cohort_c.operator_digest.v0_1"


def build_nat_cohort_c_operator_digest(
    evidence_packets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not evidence_packets:
        raise ValueError("At least one evidence packet is required")
    aggregate_references: defaultdict[str, Counter[str]] = defaultdict(Counter)
    aggregate_hold_reasons = Counter()
    candidate_count = 0
    packet_ids: list[str] = []
    for packet in evidence_packets:
        index = build_nat_cohort_c_operator_index(packet)
        packet_ids.append(str(packet.get("packet_id") or ""))
        candidate_count += index["total_candidates"]
        aggregate_hold_reasons.update(index.get("hold_reason_summary", {}))
        for ref, qualifiers in index.get("reference_summary", {}).items():
            for qualifier in qualifiers:
                aggregate_references[ref][qualifier] += 1
    reference_summary = {
        ref: dict(counter) for ref, counter in aggregate_references.items()
    }
    return {
        "schema_version": DIGEST_SCHEMA_VERSION,
        "packet_ids": packet_ids,
        "candidate_count": candidate_count,
        "hold_reason_summary": dict(aggregate_hold_reasons),
        "reference_summary": reference_summary,
    }
