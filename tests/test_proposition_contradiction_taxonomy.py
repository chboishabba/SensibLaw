from __future__ import annotations

import pytest

from src.policy.proposition_contradiction_taxonomy import (
    PROPOSITION_CONTRADICTION_LABELS,
    PROPOSITION_CONTRADICTION_TAXONOMY_VERSION,
    build_proposition_contradiction_taxonomy,
    validate_proposition_contradiction_label,
)


def test_build_proposition_contradiction_taxonomy_exposes_expected_labels_and_exclusions() -> None:
    taxonomy = build_proposition_contradiction_taxonomy()

    assert taxonomy["version"] == PROPOSITION_CONTRADICTION_TAXONOMY_VERSION
    assert taxonomy["labels"] == sorted(PROPOSITION_CONTRADICTION_LABELS)
    assert "candidate_conflict" in taxonomy["excluded_categories"]["review_pressure"]
    assert "partial_overlap" in taxonomy["excluded_categories"]["ambiguity_incompleteness"]
    assert "duplicate_root" in taxonomy["excluded_categories"]["duplicate_repetition"]
    assert "must_review" in taxonomy["excluded_categories"]["route_urgency"]


@pytest.mark.parametrize(
    "label",
    [
        "none",
        "direct_denial",
        "incompatible_assertion",
        "canonical_form_divergence",
    ],
)
def test_validate_proposition_contradiction_label_accepts_supported_labels(label: str) -> None:
    assert validate_proposition_contradiction_label(label) == label


def test_validate_proposition_contradiction_label_rejects_review_pressure_and_unknown_labels() -> None:
    with pytest.raises(ValueError, match="Unsupported proposition contradiction label"):
        validate_proposition_contradiction_label("candidate_conflict")

    with pytest.raises(ValueError, match="Unsupported proposition contradiction label"):
        validate_proposition_contradiction_label("supports")

