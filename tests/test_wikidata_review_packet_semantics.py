import json
from pathlib import Path

from src.ontology.wikidata import (
    WIKIDATA_REVIEW_PACKET_SEMANTIC_LAYER_VERSION,
    build_wikidata_review_packet,
)


def _load_nat_wdu_sandbox_source_unit_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wiki_revision_nat_wdu_sandbox_p5991_p14143_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_nat_cohort_a_split_plan_fixture() -> dict:
    fixture_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "wikidata"
        / "wikidata_nat_cohort_a_split_plan_20260401.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_review_packet_semantic_layer_is_opt_in_and_keeps_parsed_page_unchanged() -> None:
    base_packet = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
    )
    layered_packet = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        include_semantic_decomposition=True,
    )

    assert "semantic_decomposition" not in base_packet
    assert layered_packet["parsed_page"] == base_packet["parsed_page"]


def test_review_packet_semantic_layer_exposes_missing_evidence_boundary() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        include_semantic_decomposition=True,
    )

    layer = payload["semantic_decomposition"]
    assert layer["layer_schema_version"] == WIKIDATA_REVIEW_PACKET_SEMANTIC_LAYER_VERSION
    assert layer["decomposition_state"] == "surface_only"
    assert layer["separate_from_parsed_page"] is True
    assert len(layer["candidate_units"]) >= 1
    assert layer["candidate_units"][0]["unit_type"] in {
        "query_row_surface",
        "open_question_surface",
        "todo_surface",
    }
    assert "no_claim_boundary_mapping_for_candidate_units" in layer["missing_evidence"]
    assert "query_rows_not_expanded_into_fetched_semantic_units" in layer["missing_evidence"]


def test_review_packet_semantic_layer_includes_helper_surfaces_and_non_authoritative_variant_comparison() -> None:
    payload = build_wikidata_review_packet(
        source_unit_payload=_load_nat_wdu_sandbox_source_unit_fixture(),
        split_plan_payload=_load_nat_cohort_a_split_plan_fixture(),
        split_plan_id="split://Q10403939|P5991",
        include_semantic_decomposition=True,
    )

    layer = payload["semantic_decomposition"]
    assert layer["follow_depth"]["receipt_count"] == len(payload["follow_receipts"])
    assert layer["claim_boundaries"]["schema_version"].startswith("sl.wikidata_review_packet.claim_boundaries")
    assert layer["cross_source_alignment"]["schema_version"].startswith(
        "sl.wikidata_review_packet.cross_source_alignment"
    )
    assert "consensus_level" in layer["cross_source_alignment"]
    assert layer["reviewer_actions"]["can_execute_edits"] is False
    assert layer["variant_comparison"]["non_authoritative"] is True
    assert "no_comparisons_provided" not in layer["variant_comparison"]["diagnostic_flags"]
    assert layer["variant_comparison"]["comparisons"]
    assert layer["variant_comparison"]["comparisons"][0]["comparison_id"] == "split://Q10422059|P5991"
