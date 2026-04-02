from typing import Mapping, Sequence

from src.ontology.wikidata_review_packet_variant_compare import (
    compare_review_packet_variants,
)


def _base_variant() -> dict[str, object]:
    return {
        "candidate_id": "Q1|P5991|1",
        "classification": "split_required",
        "suggested_action": "review_structured_split",
        "merged_split_axes": [
            {"property": "__value__", "cardinality": 2, "reason": "multi_value"},
            {"property": "P3831", "cardinality": 1, "reason": "role"},
        ],
    }


def _variant_with_axes(axes: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "candidate_id": "Q1|P5991|2",
        "classification": "split_required",
        "suggested_action": "review_structured_split",
        "merged_split_axes": [dict(axis) for axis in axes],
    }


def test_compare_review_packet_variants_agreement() -> None:
    primary = _base_variant()
    comparison = _variant_with_axes(
        [
            {"property": "__value__", "cardinality": 2, "reason": "multi_value"},
            {"property": "P3831", "cardinality": 1, "reason": "role"},
        ]
    )

    surface = compare_review_packet_variants(
        primary_variant=primary,
        comparison_variants=[comparison],
    )

    assert surface["primary_candidate_id"] == "Q1|P5991|1"
    assert surface["diagnostic_flags"] == []
    assert surface["comparisons"][0]["status"] == "agreement"
    assert "__value__" in surface["comparisons"][0]["agreements"]


def test_compare_review_packet_variants_disagreement_and_limits() -> None:
    primary = _base_variant()
    comparison_a = _variant_with_axes(
        [
            {"property": "__value__", "cardinality": 3, "reason": "multi_value"},
            {"property": "P3831", "cardinality": 1, "reason": "role"},
        ]
    )
    comparison_b = _variant_with_axes(
        [
            {"property": "__value__", "cardinality": 2, "reason": "multi_value"},
            {"property": "P3831", "cardinality": 1, "reason": "role"},
        ]
    )
    comparison_c = _variant_with_axes(
        [
            {"property": "__value__", "cardinality": 2, "reason": "multi_value"},
            {"property": "P3831", "cardinality": 2, "reason": "role"},
        ]
    )

    surface = compare_review_packet_variants(
        primary_variant=primary,
        comparison_variants=[comparison_a, comparison_b, comparison_c],
        max_variants=2,
    )

    comparisons = surface["comparisons"]
    assert len(comparisons) == 2
    assert comparisons[0]["status"] == "disagreement"
    assert "__value__" in comparisons[0]["disagreements"]
    assert comparisons[1]["status"] == "agreement"
    assert surface["diagnostic_flags"] == []


def test_compare_review_packet_variants_missing_axes() -> None:
    surface = compare_review_packet_variants(
        primary_variant={"candidate_id": "Q1|P5991|1"},
        comparison_variants=[],
    )

    assert "primary_variant_missing_axes" in surface["diagnostic_flags"]
    assert "no_comparisons_provided" in surface["diagnostic_flags"]
