import json
from pathlib import Path

import pytest

from src.ontology.wikidata_review_packet_reviewer_actions import (
    WIKIDATA_REVIEW_PACKET_REVIEWER_ACTIONS_SCHEMA_VERSION,
    build_wikidata_review_packet_reviewer_actions,
)


def _load_nat_packet_fixture(name: str) -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / name
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_reviewer_actions_for_structured_split_packet() -> None:
    packet = _load_nat_packet_fixture("wikidata_nat_review_packet_Q10416948_sidecar_20260402.json")
    actions = build_wikidata_review_packet_reviewer_actions(packet)

    assert actions["schema_version"] == WIKIDATA_REVIEW_PACKET_REVIEWER_ACTIONS_SCHEMA_VERSION
    assert actions["packet_id"] == packet["packet_id"]
    assert actions["review_entity_qid"] == "Q10416948"
    assert actions["likely_decision"] == "review_structured_split"
    assert actions["smallest_next_check"]["check_id"] == "confirm_first_split_axis"
    assert "split_plan_requires_review" in actions["why_this_row_is_in_review"]
    assert "split_axes_detected=2" in actions["why_this_row_is_in_review"]
    assert actions["can_execute_edits"] is False


def test_build_reviewer_actions_for_review_only_packet() -> None:
    packet = _load_nat_packet_fixture("wikidata_nat_review_packet_Q56404383_sidecar_20260402.json")
    actions = build_wikidata_review_packet_reviewer_actions(packet)

    assert actions["likely_decision"] == "review_only"
    assert actions["smallest_next_check"]["check_id"] == "resolve_one_page_question"
    assert any(reason == "split_status=review_only" for reason in actions["why_this_row_is_in_review"])
    assert "uncertainty=page_open_questions" in actions["why_this_row_is_in_review"]


def test_build_reviewer_actions_requires_split_context_and_reviewer_view() -> None:
    with pytest.raises(ValueError, match="split_review_context"):
        build_wikidata_review_packet_reviewer_actions({"reviewer_view": {}})
    with pytest.raises(ValueError, match="reviewer_view"):
        build_wikidata_review_packet_reviewer_actions({"split_review_context": {}})
