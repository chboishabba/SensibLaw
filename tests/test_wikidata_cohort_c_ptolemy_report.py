from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_report_batch as report_batch


def _load_ptolemy_fixture() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_ptolemy_evidence_sample_20260405.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_ptolemy_batch_report_includes_multiple_packets() -> None:
    packet = _load_ptolemy_fixture()
    other_packet = _load_ptolemy_fixture()
    batch = report_batch.build_nat_cohort_c_operator_report_batch([packet, other_packet])
    assert batch["batch_candidate_count"] == 6
    assert len(batch["packet_ids"]) == 2
    assert "P854 https://www.wikidata.org/wiki/Q4000001" in batch["reference_anchors"]
    assert batch["hold_reason_summary"]
