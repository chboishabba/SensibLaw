from __future__ import annotations

from scripts.review_geometry_profiles import get_normalized_profile


def test_normalized_review_profiles_capture_shared_policy() -> None:
    au = get_normalized_profile("au")
    wikidata = get_normalized_profile("wikidata")
    gwb = get_normalized_profile("gwb")

    assert au["review_item_status_map"]["unsupported_affidavit"] == "review_required"
    assert au["primary_workload_map"]["chronology_gap"] == "event_or_time_pressure"

    assert wikidata["source_status_map"]["review_required"] == "review_required"
    assert wikidata["primary_workload_map"]["governance_gap"] == "governance_pressure"

    assert gwb["review_item_status_map"]["partial"] == "review_required"
    assert gwb["primary_workload_map"]["surface_resolution_gap"] == "linkage_pressure"
