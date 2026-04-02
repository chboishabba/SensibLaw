from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_evidence as evidence


def _load_fixture() -> dict[str, object]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "wikidata" / "wikidata_nat_cohort_c_operator_packet_extension_20260403.json"
    candidates = json.loads(fixture_path.read_text(encoding="utf-8"))
    return {
        "lane_id": "wikidata_nat_wdu_p5991_p14143",
        "cohort_id": "non_ghg_protocol_or_missing_p459",
        "scan_status": "live_population_scan_preview",
        "sample_candidates": candidates,
        "summary": {"p459_status_counts": {"missing": 2, "non-ghg-protocol": 1}},
    }


def test_operator_evidence_packet_from_preview_fixture() -> None:
    payload = _load_fixture()
    packet = evidence.build_nat_cohort_c_operator_evidence_packet(payload)
    rows = packet["evidence_rows"]
    assert packet["summary"]["candidate_count"] == len(rows)
    assert all(row["promotion_guard"] == "hold" for row in rows)
    qids = [row["qid"] for row in rows]
    assert qids == sorted(qids)
    assert len({row["evidence_id"] for row in rows}) == len(rows)
    first_row = rows[0]
    assert first_row["hold_gate"] == "review_first_population_scan"
    assert first_row["qualifier_hint"]
    assert "operator_hold_reason" in first_row
