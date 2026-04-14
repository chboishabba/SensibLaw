from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.ontology.wikidata_nat_live_follow_executor import (
    LIVE_FOLLOW_RESULT_SCHEMA_VERSION,
    POLICY_RISK_PREFLIGHT_SCHEMA_VERSION,
    build_policy_risk_population_preview_preflight,
    execute_split_heavy_business_family_lane,
    execute_wikidata_nat_live_follow_campaign,
)


def _load_campaign_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_live_follow_campaign_20260403.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_execute_nat_live_follow_campaign_fetches_revision_locked_rows() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        if "w/api.php" in url:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "revisions": [
                                {"revid": 2474420124, "timestamp": "2026-04-01T12:00:00Z"},
                                {"revid": 2474419999, "timestamp": "2026-03-31T12:00:00Z"},
                            ]
                        }
                    }
                }
            }
        if "Special:EntityData" in url:
            return {
                "entities": {
                    "Q10403939": {
                        "labels": {"en": {"value": "Example company"}},
                        "claims": {"P31": [], "P5991": []},
                    }
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        category_ids=["hard_grounding_packet"],
        fetch_json=fake_fetch_json,
    )

    assert result["schema_version"] == LIVE_FOLLOW_RESULT_SCHEMA_VERSION
    assert result["selected_count"] == 1
    assert result["status_counts"] == {"fetched": 1}
    row = result["result_rows"][0]
    assert row["category_id"] == "hard_grounding_packet"
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_revision_locked_source"
    assert row["evidence"]["revision"]["revision_id"] == "2474420124"
    assert row["evidence"]["entity_summary"]["claim_property_count"] == 2


def test_policy_risk_population_preview_preflight_ranks_candidates() -> None:
    campaign = _load_campaign_fixture()
    report = build_policy_risk_population_preview_preflight(campaign)

    assert report["schema_version"] == POLICY_RISK_PREFLIGHT_SCHEMA_VERSION
    assert report["top_n"] == 2
    assert report["candidate_count"] == 2
    assert report["stop_conditions"] == ["policy-risk hold is better justified or narrowed"]
    assert report["coverage_counts"]["hold"] == 2
    qids = {candidate["qid"] for candidate in report["candidates"]}
    assert qids == {"Q1000001", "Q1000002"}
    first_candidate = report["candidates"][0]
    assert set(first_candidate["routing_needs"]) >= {"authority", "reference", "follow"}
    assert first_candidate["coverage_status"] == "hold"


def test_policy_risk_population_preview_preflight_reports_missing_evidence() -> None:
    campaign = copy.deepcopy(_load_campaign_fixture())
    campaign["categories"].append(
        {
            "category_id": "policy_risk_population_preview",
            "uncertainty_kind": "policy_hold_vs_narrower_review_path",
            "targets": [{"qid": "Q999999", "statement_id": "Q999999-1"}],
            "preferred_source_order": ["named_reference_url", "named_revision_locked_source"],
            "max_hops": 2,
            "stop_condition": "policy-risk hold still applies",
        }
    )

    report = build_policy_risk_population_preview_preflight(campaign, top_n=3)
    assert report["candidate_count"] == 3
    assert "missing_policy_risk_evidence" in report["failure_modes"]


def test_execute_nat_live_follow_campaign_falls_through_query_link_fetch_error() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        if "w/api.php" in url:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "revisions": [
                                {"revid": 123, "timestamp": "2026-04-01T12:00:00Z"},
                            ]
                        }
                    }
                }
            }
        if "Special:EntityData" in url:
            return {
                "entities": {
                    "Q738421": {
                        "labels": {"en": {"value": "Example split item"}},
                        "claims": {"P31": []},
                    }
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        raise RuntimeError(f"query link unavailable for {url}")

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        category_ids=["split_heavy_business_family"],
        limit=1,
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    assert result["selected_count"] == 1
    row = result["result_rows"][0]
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_revision_locked_source"
    assert row["attempts"][0]["status"] == "fetch_error"
    assert row["attempts"][0]["source_class"] == "named_query_link"


def test_execute_nat_live_follow_campaign_fetches_named_query_link_when_available() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        raise AssertionError(f"unexpected JSON fetch {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        assert url == "https://w.wiki/KR5d"
        return (
            "https://query.wikidata.org/#bounded",
            "text/html; charset=utf-8",
            "<html><head><title>Bounded query result</title></head><body>bounded query evidence</body></html>",
        )

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        category_ids=["split_heavy_business_family"],
        limit=1,
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    row = result["result_rows"][0]
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_query_link"
    assert row["attempts"][0]["status"] == "fetched"
    assert row["evidence"]["query_link"]["original_url"] == "https://w.wiki/KR5d"
    assert row["evidence"]["query_link"]["final_url"] == "https://query.wikidata.org/#bounded"
    assert row["evidence"]["query_link"]["title"] == "Bounded query result"


def test_execute_nat_live_follow_campaign_falls_back_when_query_link_fetch_fails() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        if "w/api.php" in url:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "revisions": [
                                {"revid": 123, "timestamp": "2026-04-01T12:00:00Z"},
                            ]
                        }
                    }
                }
            }
        if "Special:EntityData" in url:
            return {
                "entities": {
                    "Q10422059": {
                        "labels": {"en": {"value": "Atrium Ljungberg"}},
                        "claims": {"P31": []},
                    }
                }
            }
        raise AssertionError(f"unexpected URL {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        raise RuntimeError(f"query-link fetch failed for {url}")

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        plan_ids=["split_heavy_business_family:2"],
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    row = result["result_rows"][0]
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_revision_locked_source"
    assert row["attempts"][0]["status"] == "fetch_error"
    assert row["attempts"][0]["source_class"] == "named_query_link"
    assert "query-link fetch failed" in row["attempts"][0]["reason"]


def test_execute_nat_live_follow_campaign_fetches_named_reference_url_when_available() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        raise AssertionError(f"unexpected JSON fetch {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        assert url == "https://www.wikidata.org/wiki/Q1000001"
        return (
            url,
            "text/html; charset=utf-8",
            "<html><head><title>Q1000001 page</title></head><body>reference anchored policy-risk evidence</body></html>",
        )

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        category_ids=["policy_risk_population_preview"],
        limit=1,
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    row = result["result_rows"][0]
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_reference_url"
    assert row["attempts"][0]["status"] == "fetched"
    assert row["evidence"]["reference_url"]["original_url"] == "https://www.wikidata.org/wiki/Q1000001"


def test_execute_nat_live_follow_campaign_fetches_reference_url_from_cohort_b_packet_input() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        raise AssertionError(f"unexpected JSON fetch {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        assert url == "https://www.wikidata.org/wiki/Q11661"
        return (
            url,
            "text/html; charset=utf-8",
            "<html><head><title>Q11661 page</title></head><body>cohort b variance evidence</body></html>",
        )

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        plan_ids=["reconciled_non_business_variance:2"],
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    row = result["result_rows"][0]
    assert row["status"] == "fetched"
    assert row["chosen_source_class"] == "named_reference_url"
    assert row["attempts"][0]["status"] == "fetched"
    assert row["attempts"][0]["source_class"] == "named_reference_url"
    assert row["evidence"]["reference_url"]["original_url"] == "https://www.wikidata.org/wiki/Q11661"


def test_execute_nat_live_follow_campaign_preserves_fetch_error_over_unsupported_fallbacks() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        raise RuntimeError("network down")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        raise RuntimeError("network down")

    result = execute_wikidata_nat_live_follow_campaign(
        campaign,
        category_ids=["hard_grounding_packet"],
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    row = result["result_rows"][0]
    assert row["status"] == "fetch_error"
    assert row["chosen_source_class"] == "named_revision_locked_source"
    assert row["evidence"]["status"] == "fetch_error"
    assert row["attempts"][0]["status"] == "fetch_error"


def test_execute_split_heavy_lane_filters_to_category_and_preserves_order() -> None:
    campaign = _load_campaign_fixture()

    def fake_fetch_json(url: str, *, params=None, timeout_seconds: int = 30):
        raise AssertionError(f"unexpected JSON fetch {url}")

    def fake_fetch_text(url: str, *, timeout_seconds: int = 30):
        return (
            url,
            "text/html; charset=utf-8",
            "<html><head><title>split-heavy query</title></head><body>bounded evidence</body></html>",
        )

    result = execute_split_heavy_business_family_lane(
        campaign,
        fetch_json=fake_fetch_json,
        fetch_text=fake_fetch_text,
    )

    assert result["selected_count"] == 2
    assert all(row["category_id"] == "split_heavy_business_family" for row in result["result_rows"])
    for row in result["result_rows"]:
        attempts = row["attempts"]
        assert attempts
        assert attempts[0]["source_class"] == "named_query_link"


def test_execute_split_heavy_lane_rejects_unbounded_search() -> None:
    campaign = _load_campaign_fixture()
    for category in campaign.get("categories", []):
        if category.get("category_id") == "split_heavy_business_family":
            category["preferred_source_order"] = [
                "bounded_live_search",
                "named_revision_locked_source",
            ]
            break

    with pytest.raises(ValueError, match="bounded_live_search"):
        execute_split_heavy_business_family_lane(campaign)
