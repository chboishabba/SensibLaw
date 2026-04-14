from __future__ import annotations

import pytest

from src.sources.case_record.state_case_lane import (
    STATE_CASES,
    build_state_case_follow,
)


def test_build_state_case_follow_honors_contract():
    key = "case:us:ca:supreme:2008:mitchell"
    result = build_state_case_follow(key)

    assert result["state_case_key"] == key
    assert result["source_family"] == STATE_CASES[key]["source_family"]
    assert result["state_case"]["court"] == "Supreme Court of California"
    assert "domestic_overlays" in result
    overlays = result["domestic_overlays"]
    assert overlays == STATE_CASES[key]["domestic_overlay"]
    normalized = result["normalized_follow_input"]
    assert normalized["court"].startswith("Supreme Court")
    assert "42 Cal.4th" in STATE_CASES[key]["citation"]
    assert "crossrefs" in normalized
    assert result["follow_contract"]["scope"].startswith("bounded")


def test_build_state_case_follow_missing_case():
    with pytest.raises(KeyError):
        build_state_case_follow("case:us:missing")
