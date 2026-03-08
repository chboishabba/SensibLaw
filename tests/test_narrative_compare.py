from __future__ import annotations

from pathlib import Path

from src.reporting.narrative_compare import (
    build_narrative_comparison_report,
    build_narrative_validation_report,
    load_fixture_sources,
)


def _fixture_sources() -> tuple[dict, list]:
    fixture_path = Path("SensibLaw/demo/narrative/friendlyjordies_demo.json")
    return load_fixture_sources(fixture_path)


def test_friendlyjordies_fixture_builds_validation_report() -> None:
    _, sources = _fixture_sources()
    report = build_narrative_validation_report(sources[0])
    assert report["source"]["source_id"] == "jordies_video"
    assert report["summary"]["fact_count"] >= 2
    assert report["summary"]["proposition_link_count"] >= 2
    assert any(row["predicate_key"] == "happen_in" for row in report["propositions"])
    assert any(row["predicate_key"] == "approve_after" for row in report["propositions"])
    assert any(link["link_kind"] == "attributes_to" for link in report["proposition_links"])
    assert any(ref["label"] == "Court records" for ref in report["corroboration_refs"])


def test_friendlyjordies_fixture_comparison_surfaces_shared_and_disputed_rows() -> None:
    _, sources = _fixture_sources()
    comparison = build_narrative_comparison_report(sources[0], sources[1])
    assert comparison["summary"]["shared_proposition_count"] >= 1
    assert comparison["summary"]["disputed_proposition_count"] >= 1
    assert any(
        row["left"]["predicate_key"] == "approve_after" and row["right"]["predicate_key"] == "begin_before"
        for row in comparison["disputed_propositions"]
    )
    assert any("FriendlyJordies" in ",".join(row["left_attributions"]) for row in comparison["link_differences"])
    assert any("The newspaper" in ",".join(row["right_attributions"]) for row in comparison["link_differences"])
    assert comparison["source_only_propositions"]["jordies_video"] == []
    assert comparison["source_only_propositions"]["newspaper_report"] == []
