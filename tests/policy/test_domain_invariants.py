from __future__ import annotations

import pytest

from src.policy.domain_invariants import (
    build_invariant_contribution_receipt,
    build_invariant_revision,
    build_trusted_conforming_member,
)


def _member() -> dict[str, object]:
    return build_trusted_conforming_member(
        candidate_ref="candidate:1",
        source_revision_ref="wikidata:Q1@123",
        review_disposition="confirmed_conformant_after_split",
        review_decision_ref="review:1",
        reviewer_authority_ref="reviewer:climate-team",
        coverage_state="observed",
        source_statement_refs=["Q1$abc"],
        conformance_context_ref="context:Q1:P5991:annual-report",
        dependency_group_ref="dependency-group:Q1:annual-report",
        feature_contributions=[
            {
                "feature": "unit",
                "value": "Q57084901",
                "evidence_refs": ["Q1$abc"],
            },
            {
                "feature": "scope_shape",
                "condition": "annual_total",
                "value": "single_scope",
            },
        ],
    )


def test_reviewed_member_builds_deterministic_invariant_revision() -> None:
    receipt = build_invariant_contribution_receipt(
        _member(), domain_invariant_ref="wikidata:climate:v1"
    )
    result = build_invariant_revision(
        domain_invariant_ref="wikidata:climate:v1",
        policy_model_ref="policy:P14143",
        policy_requirements=[{"feature": "subject", "value": "company"}],
        contribution_receipts=[receipt],
        reviewer_authority_ref="reviewer:climate-team",
        coverage_requirements=["P31", "P585", "P459"],
    )

    snapshot = result["snapshot"]
    assert snapshot["trusted_member_refs"] == ["candidate:1"]
    assert snapshot["empirical_features"] == [
        {
            "confirmed_member_count": 1,
            "confirmed_member_refs": ["candidate:1"],
            "confirmed_dependency_group_count": 1,
            "confirmed_dependency_group_refs": ["dependency-group:Q1:annual-report"],
            "evidence_refs": [],
            "feature": "scope_shape",
            "condition": "annual_total",
            "value": "single_scope",
        },
        {
            "confirmed_member_count": 1,
            "confirmed_member_refs": ["candidate:1"],
            "confirmed_dependency_group_count": 1,
            "confirmed_dependency_group_refs": ["dependency-group:Q1:annual-report"],
            "evidence_refs": ["Q1$abc"],
            "feature": "unit",
            "value": "Q57084901",
        },
    ]
    assert snapshot["promotion_effect"] == "not_evaluated"
    assert result["revision_receipt"]["new_snapshot_ref"] == snapshot["snapshot_id"]


@pytest.mark.parametrize(
    ("review_disposition", "coverage_state"),
    [
        ("A", "observed"),
        ("held", "observed"),
        ("confirmed_model_conformant", "incomplete"),
    ],
)
def test_unreviewed_or_incomplete_rows_cannot_join_trusted_cohort(
    review_disposition: str, coverage_state: str
) -> None:
    with pytest.raises(ValueError):
        build_trusted_conforming_member(
            candidate_ref="candidate:1",
            source_revision_ref="wikidata:Q1@123",
            review_disposition=review_disposition,
            review_decision_ref="review:1",
            reviewer_authority_ref="reviewer:climate-team",
            coverage_state=coverage_state,
            feature_contributions=[{"feature": "unit", "value": "Q57084901"}],
        )


def test_context_witness_requires_a_dependency_group() -> None:
    with pytest.raises(ValueError, match="dependency_group_ref"):
        build_trusted_conforming_member(
            candidate_ref="candidate:1",
            source_revision_ref="wikidata:Q1@123",
            review_disposition="confirmed_model_conformant",
            review_decision_ref="review:1",
            reviewer_authority_ref="reviewer:climate-team",
            coverage_state="observed",
            feature_contributions=[{"feature": "unit", "value": "Q57084901"}],
            conformance_context_ref="context:Q1:P5991",
        )


def test_shared_dependency_group_does_not_inflate_independent_observation_count() -> (
    None
):
    first = _member()
    second = build_trusted_conforming_member(
        candidate_ref="candidate:2",
        source_revision_ref="wikidata:Q1@123",
        review_disposition="confirmed_model_conformant",
        review_decision_ref="review:2",
        reviewer_authority_ref="reviewer:climate-team",
        coverage_state="observed",
        source_statement_refs=["Q1$def"],
        conformance_context_ref="context:Q1:P5991:annual-report",
        dependency_group_ref="dependency-group:Q1:annual-report",
        feature_contributions=[{"feature": "unit", "value": "Q57084901"}],
    )
    result = build_invariant_revision(
        domain_invariant_ref="wikidata:climate:v1",
        policy_model_ref="policy:P14143",
        policy_requirements=[],
        contribution_receipts=[
            build_invariant_contribution_receipt(
                first, domain_invariant_ref="wikidata:climate:v1"
            ),
            build_invariant_contribution_receipt(
                second, domain_invariant_ref="wikidata:climate:v1"
            ),
        ],
        reviewer_authority_ref="reviewer:climate-team",
    )

    unit_feature = next(
        feature
        for feature in result["snapshot"]["empirical_features"]
        if feature["feature"] == "unit"
    )
    assert unit_feature["confirmed_member_count"] == 2
    assert unit_feature["confirmed_dependency_group_count"] == 1
