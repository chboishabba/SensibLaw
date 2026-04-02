from __future__ import annotations

import json
from pathlib import Path

from src.ontology import wikidata_cohort_c_operator_index as operator_index


def _load_evidence_packet() -> dict[str, object]:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_c_ptolemy_evidence_sample_20260405.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_operator_index_summary_lists_reference_qualifiers_and_hold_reasons() -> None:
    packet = _load_evidence_packet()
    index = operator_index.build_nat_cohort_c_operator_index(packet)
    assert index["total_candidates"] == len(packet["evidence_rows"])
    assert "reference_summary" in index
    for ref, qualifiers in index["reference_summary"].items():
        assert qualifiers
    assert index["hold_reason_summary"]
