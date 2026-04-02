from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_report_batch as report_batch


def _load_packet_fixture() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_operator_evidence_packet_20260404.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_batch_report_combines_hold_reasons() -> None:
    packet = _load_packet_fixture()
    batch = report_batch.build_nat_cohort_c_operator_report_batch([packet, packet])
    assert batch["batch_candidate_count"] == 2 * len(packet["evidence_rows"])
    assert batch["hold_reason_summary"]
    assert "P854 https://www.wikidata.org/wiki/Q1000001" in batch["reference_anchors"]
