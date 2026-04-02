from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_digest as digest


def _load_packets() -> list[dict[str, object]]:
    base = Path(__file__).resolve().parent / "fixtures" / "wikidata"
    paths = [
        base / "wikidata_nat_cohort_c_operator_evidence_packet_20260404.json",
        base / "wikidata_nat_cohort_c_ptolemy_evidence_sample_20260405.json",
    ]
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def test_operator_digest_aggregates_reference_qualifier_counts() -> None:
    packets = _load_packets()
    report = digest.build_nat_cohort_c_operator_digest(packets)
    assert report["candidate_count"] == sum(
        len(packet["evidence_rows"]) for packet in packets
    )
    assert "hold_reason_summary" in report
    assert report["reference_summary"]
    assert len(report["packet_ids"]) == 2
