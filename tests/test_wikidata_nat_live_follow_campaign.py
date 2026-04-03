from __future__ import annotations

import json
from pathlib import Path


def _load_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_nat_live_follow_campaign_spans_multiple_uncertainty_categories() -> None:
    payload = _load_fixture()

    assert payload["campaign_id"] == "wikidata_nat_live_follow_campaign_20260403"
    assert payload["lane_id"] == "wikidata_nat_wdu_p5991_p14143"
    assert payload["campaign_rule"] == "local_packet_first_bounded_live_follow_only"

    categories = payload["categories"]
    assert len(categories) >= 5
    assert {
        "hard_grounding_packet",
        "split_heavy_business_family",
        "reconciled_non_business_variance",
        "policy_risk_population_preview",
        "missing_instance_of_typing_deficit",
        "unreconciled_instance_of_split_axis",
    }.issubset({category["category_id"] for category in categories})


def test_nat_live_follow_campaign_keeps_bounded_source_order_and_stop_conditions() -> None:
    payload = _load_fixture()

    for category in payload["categories"]:
        assert category["targets"]
        assert category["preferred_source_order"]
        assert category["preferred_source_order"][0].startswith("named_")
        assert category["max_hops"] == 2
        assert category["stop_condition"]
