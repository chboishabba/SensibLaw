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


def _chat_argument_sources() -> tuple[dict, list]:
    fixture_path = Path("SensibLaw/demo/narrative/friendlyjordies_chat_arguments.json")
    return load_fixture_sources(fixture_path)


def _authority_wrapper_sources() -> tuple[dict, list]:
    fixture_path = Path("SensibLaw/demo/narrative/friendlyjordies_authority_wrappers.json")
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


def test_chat_derived_jordies_argument_fixture_extracts_multiple_argument_predicates() -> None:
    _, sources = _chat_argument_sources()
    report = build_narrative_validation_report(sources[0])
    predicates = {row["predicate_key"] for row in report["propositions"]}
    assert "block" in predicates
    assert "contribute_to" in predicates
    assert "use" in predicates
    assert "support" in predicates
    support_links = [row for row in report["proposition_links"] if row["link_kind"] == "supports"]
    assert any(
        any(receipt["value"] == "block_subject_embeds_causal_subject" for receipt in row["receipts"])
        for row in support_links
    )
    assert any(
        any(receipt["value"] == "documentary_support_same_signature" for receipt in row["receipts"])
        for row in support_links
    )


def test_chat_derived_jordies_argument_fixture_surfaces_causal_dispute() -> None:
    _, sources = _chat_argument_sources()
    comparison = build_narrative_comparison_report(sources[0], sources[1])
    assert comparison["summary"]["shared_proposition_count"] >= 2
    assert comparison["summary"]["disputed_proposition_count"] >= 1
    assert comparison["summary"]["comparison_link_count"] >= 1
    assert any(
        row["left"]["predicate_key"] == "contribute_to"
        and row["right"]["predicate_key"] == "contribute_to"
        for row in comparison["disputed_propositions"]
    )
    assert any(
        row["predicate_key"] == "support" for row in comparison["source_only_propositions"]["jordies_case"]
    )
    assert any(
        row["predicate_key"] == "govern_in" for row in comparison["source_only_propositions"]["counter_analysis"]
    )
    assert any(
        row["link_kind"] == "supports"
        for row in comparison["reports"]["jordies_case"]["proposition_links"]
    )
    assert any(
        row["link_kind"] == "supports"
        for row in comparison["reports"]["counter_analysis"]["proposition_links"]
    )
    assert any(
        row["link_kind"] == "undermines"
        and any(receipt["value"] == "shared_outcome_conflicting_cause_or_predicate" for receipt in row["receipts"])
        for row in comparison["comparison_links"]
    )


def test_nested_authority_wrappers_emit_separate_hold_and_assert_nodes() -> None:
    _, sources = _authority_wrapper_sources()
    report = build_narrative_validation_report(sources[0])
    assert any(
        row["predicate_key"] == "hold" and row["proposition_kind"] == "attribution"
        for row in report["propositions"]
    )
    assert any(
        row["predicate_key"] == "assert" and row["proposition_kind"] == "attribution"
        for row in report["propositions"]
    )
    assert sum(1 for row in report["proposition_links"] if row["link_kind"] == "attributes_to") >= 4


def test_nested_authority_wrappers_preserve_full_attribution_chain_in_comparison() -> None:
    _, sources = _authority_wrapper_sources()
    comparison = build_narrative_comparison_report(sources[0], sources[1])
    block_shared = next(
        row for row in comparison["shared_propositions"] if row["signature"] == "block||object=cprs|subject=greens"
    )
    assert any("hold:the majority in Lepore" == value for value in block_shared["left_attributions"])
    assert any("assert:FriendlyJordies" == value for value in block_shared["left_attributions"])
    assert any("hold:the majority in Lepore" == value for value in block_shared["right_attributions"])
    assert any("report:The analysis" == value for value in block_shared["right_attributions"])
