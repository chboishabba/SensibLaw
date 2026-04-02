from __future__ import annotations

import json
from pathlib import Path


def test_operator_packet_extension_fixture_valid() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "wikidata" / "wikidata_nat_cohort_c_operator_packet_extension_20260403.json"
    candidates = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(candidates, list)
    for candidate in candidates:
        assert candidate["hold_gate"] == "review_first_population_scan"
        assert candidate["p459_status"] in {"missing", "non-ghg-protocol"}
        assert candidate["operator_hold_reason"]
        assert candidate["preview_hold_reason"]
        assert candidate["qualifier_hint"]
