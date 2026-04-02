from __future__ import annotations

import json
from pathlib import Path


def test_cohort_c_live_preview_extension_fixture_shape() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "wikidata" / "wikidata_nat_cohort_c_live_preview_extension_20260402.json"
    candidates = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(candidates, list)
    required_keys = {
        "qid",
        "label",
        "p459_status",
        "preview_hold_reason",
        "hold_gate",
        "notes",
    }
    for candidate in candidates:
        assert required_keys.issubset(candidate.keys())
        assert candidate["hold_gate"] == "review_first_population_scan"
        assert candidate["p459_status"] in {"missing", "non-ghg-protocol"}
        assert candidate["preview_hold_reason"]
