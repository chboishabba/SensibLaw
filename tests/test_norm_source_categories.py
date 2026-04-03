from __future__ import annotations

from src.sources.norm_source_categories import canonical_norm_source_categories


def test_norm_source_categories_cover_expected_types() -> None:
    categories = canonical_norm_source_categories()
    identifiers = {category["identifier"] for category in categories}
    assert {"standard", "inquiry_report", "regulatory_guidance", "policy_framework"} <= identifiers
    assert all(category["enforcement_level"] == "soft" for category in categories)
    assert all(category["influence_type"] in {"normative", "evidentiary", "directive", "strategic"} for category in categories)
