from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_report as report


def _load_packet_fixture() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_operator_packet_extension_20260403.json"
    )
    sample_candidates = json.loads(fixture_path.read_text(encoding="utf-8"))
    packet = {
        "schema_version": "sl.wikidata_nat.cohort_c.operator_evidence.v0_1",
        "packet_id": "operator-evidence:test",
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "non_ghg_protocol_or_missing_p459",
        "scan_status": "live_population_scan_preview",
        "evidence_rows": sample_candidates,
    }
    return packet


def test_operator_report_summarizes_hold_reasons_and_refs() -> None:
    packet = _load_packet_fixture()
    summary = report.build_nat_cohort_c_operator_report(packet)
    assert summary["candidate_count"] == len(packet["evidence_rows"])
    assert "Operator hold reason" not in summary  # ensure we only return counts/anchors
    assert summary["hold_reason_summary"]
    assert summary["reference_anchors"]
