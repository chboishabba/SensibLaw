from __future__ import annotations

import pytest

from src.policy.review_confirmation import (
    build_review_confirmation,
    build_trusted_member_from_confirmation,
)


def _split_confirmation() -> dict[str, object]:
    return build_review_confirmation(
        candidate_ref="candidate:Q1:P5991:1",
        source_revision_ref="wikidata:Q1@123",
        review_packet_ref="packet:Q1:split",
        review_disposition="confirmed_conformant_after_split",
        reviewer_authority_ref="reviewer:climate-team",
        coverage_state="observed",
        decision_summary="Approved the annual scope split after checking the source statement family.",
        approved_split_plan_ref="split-plan:Q1:annual-scope",
        source_statement_refs=["Q1$abc"],
        conformance_context_ref="context:Q1:P5991:annual-report",
        dependency_group_ref="dependency-group:Q1:annual-report",
        feature_contributions=[
            {"feature": "unit", "value": "Q57084901"},
            {
                "feature": "scope_shape",
                "condition": "annual_total",
                "value": "single_scope",
            },
        ],
    )


def test_approved_split_becomes_a_trusted_member_without_edit_effect() -> None:
    confirmation = _split_confirmation()
    member = build_trusted_member_from_confirmation(confirmation)

    assert confirmation["approved_split_plan_ref"] == "split-plan:Q1:annual-scope"
    assert confirmation["promotion_effect"] == "not_evaluated"
    assert confirmation["edit_effect"] == "none"
    assert member["review_decision_ref"] == confirmation["review_decision_ref"]
    assert member["review_disposition"] == "confirmed_conformant_after_split"
    assert member["conformance_context_ref"] == "context:Q1:P5991:annual-report"
    assert member["dependency_group_ref"] == "dependency-group:Q1:annual-report"


def test_split_confirmation_requires_approved_plan() -> None:
    with pytest.raises(ValueError, match="approved_split_plan_ref"):
        build_review_confirmation(
            candidate_ref="candidate:Q1:P5991:1",
            source_revision_ref="wikidata:Q1@123",
            review_packet_ref="packet:Q1:split",
            review_disposition="confirmed_conformant_after_split",
            reviewer_authority_ref="reviewer:climate-team",
            coverage_state="observed",
            decision_summary="Approved.",
            feature_contributions=[{"feature": "unit", "value": "Q57084901"}],
        )


def test_unconfirmed_family_label_cannot_be_a_review_confirmation() -> None:
    with pytest.raises(ValueError, match="confirmed disposition"):
        build_review_confirmation(
            candidate_ref="candidate:Q1:P5991:1",
            source_revision_ref="wikidata:Q1@123",
            review_packet_ref="packet:Q1:split",
            review_disposition="B",
            reviewer_authority_ref="reviewer:climate-team",
            coverage_state="observed",
            decision_summary="Classifier says B.",
            feature_contributions=[{"feature": "unit", "value": "Q57084901"}],
        )
