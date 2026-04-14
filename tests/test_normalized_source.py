from __future__ import annotations

from src.sources.normalized_source import build_normalized_source_unit


def test_normalized_source_unit_contains_required_fields() -> None:
    normalized = build_normalized_source_unit(
        source_id="legislation.gov.uk:1:enacted",
        source_family="uk_legislation",
        jurisdiction="uk",
        authority_level="statute",
        source_type="section",
        title="EUWA section 1",
        url="https://www.legislation.gov.uk/ukpga/2018/16/section/1/enacted",
        section="1",
        version="enacted",
        live_status="live",
        provenance="legislation.gov.uk",
    )
    assert normalized["source_family"] == "uk_legislation"
    assert normalized["jurisdiction"] == "uk"
    assert normalized["section"] == "1"
    assert normalized["translation_status"] == "original"
    assert normalized["primary_language"] == "en"
    assert "provenance" in normalized
