import pytest

from src.ontology.wikidata_review_packet_claim_boundaries import (
    WIKIDATA_REVIEW_PACKET_CLAIM_BOUNDARY_SCHEMA_VERSION,
    build_review_packet_claim_boundaries,
)


def _sample_source_surface() -> dict:
    return {
        "source_unit_id": "source:1",
        "source_entity_qid": "Q10403939",
        "anchor_refs": [
            {
                "anchor_id": "a2",
                "start": 40,
                "end": 75,
                "label": "expected_qualifier_family",
                "text_excerpt": "qualifiers include scope, method, and time dimensions",
            },
            {
                "anchor_id": "a1",
                "start": 10,
                "end": 30,
                "label": "query_surface",
                "text_excerpt": "all carbon footprint statements",
            },
        ],
    }


def _sample_split_review_context() -> dict:
    return {
        "split_plan_id": "split://Q10403939|P5991",
        "merged_split_axes": [
            {"property": "P518", "source": "slot", "reason": "multi_valued_dimension", "cardinality": 3},
            {"property": "P580", "source": "slot", "reason": "multi_valued_dimension", "cardinality": 2},
        ],
    }


def test_build_review_packet_claim_boundaries_maps_anchors_and_axes() -> None:
    payload = build_review_packet_claim_boundaries(
        source_surface=_sample_source_surface(),
        split_review_context=_sample_split_review_context(),
        page_signals={"unresolved_questions": ["Is scope 3 merged with scope 2?"]},
    )

    assert payload["schema_version"] == WIKIDATA_REVIEW_PACKET_CLAIM_BOUNDARY_SCHEMA_VERSION
    assert payload["decomposition_state"] == "candidate_only"
    assert "not_full_semantic_decomposition" in payload["non_claims"]
    assert payload["summary"] == {
        "anchor_count": 2,
        "axis_count": 2,
        "candidate_boundary_count": 2,
        "unresolved_question_count": 1,
    }
    first = payload["candidate_claim_boundaries"][0]
    assert first["anchor_ref"]["anchor_id"] == "a1"
    assert first["axis_signals"][0]["property"] == "P518"
    assert "no_clause_level_segmentation" in first["missing_evidence"]
    assert "open_questions_unresolved" in first["missing_evidence"]


def test_build_review_packet_claim_boundaries_produces_axis_only_candidate_without_anchors() -> None:
    payload = build_review_packet_claim_boundaries(
        source_surface={"anchor_refs": []},
        split_review_context=_sample_split_review_context(),
    )

    assert payload["summary"]["anchor_count"] == 0
    assert payload["summary"]["axis_count"] == 2
    assert payload["summary"]["candidate_boundary_count"] == 1
    only = payload["candidate_claim_boundaries"][0]
    assert only["anchor_ref"] is None
    assert only["axis_signals"][1]["property"] == "P580"
    assert "no_anchor_refs_for_axis_mapping" in only["missing_evidence"]


def test_build_review_packet_claim_boundaries_fails_closed_on_invalid_shape() -> None:
    with pytest.raises(ValueError, match="source_surface\\.anchor_refs must be a list"):
        build_review_packet_claim_boundaries(
            source_surface={"anchor_refs": "bad"},
            split_review_context=_sample_split_review_context(),
        )

    with pytest.raises(ValueError, match="split_review_context\\.merged_split_axes must be a list"):
        build_review_packet_claim_boundaries(
            source_surface=_sample_source_surface(),
            split_review_context={"merged_split_axes": "bad"},
        )
