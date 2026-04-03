from __future__ import annotations

import json
from pathlib import Path

from src.ontology.wikidata_nat_live_follow_campaign import (
    CAMPAIGN_PLAN_SCHEMA_VERSION,
    build_wikidata_nat_live_follow_campaign_plan,
)


def _load_campaign_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_nat_live_follow_campaign_plan_uses_all_categories() -> None:
    campaign = _load_campaign_fixture()
    plan = build_wikidata_nat_live_follow_campaign_plan(campaign)

    assert plan["schema_version"] == CAMPAIGN_PLAN_SCHEMA_VERSION
    assert plan["campaign_id"] == campaign["campaign_id"]
    assert plan["campaign_rule"] == "local_packet_first_bounded_live_follow_only"
    assert plan["plan_count"] == 11
    assert plan["category_counts"]["hard_grounding_packet"] == 1
    assert plan["category_counts"]["split_heavy_business_family"] == 2
    assert plan["category_counts"]["reconciled_non_business_variance"] == 2
    assert plan["category_counts"]["policy_risk_population_preview"] == 2
    assert plan["category_counts"]["missing_instance_of_typing_deficit"] == 2
    assert plan["category_counts"]["unreconciled_instance_of_split_axis"] == 2


def test_build_nat_live_follow_campaign_plan_emits_bounded_rows() -> None:
    campaign = _load_campaign_fixture()
    plan = build_wikidata_nat_live_follow_campaign_plan(campaign)

    first = plan["plan_rows"][0]
    assert first["execution_mode"] == "bounded_live_follow"
    assert first["local_first"] is True
    assert first["preferred_source_class"].startswith("named_")
    assert first["max_hops"] == 2
    assert first["trigger"].startswith("live_follow:")
    assert first["stop_condition"]
