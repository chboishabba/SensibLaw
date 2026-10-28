from __future__ import annotations

import pytest

from src.policy.alignment_readiness_assessment import targeting_promotion_allowed
from src.policy.review_targeting_contract import (
    build_targeting_alternatives_from_resolution_artifacts,
    build_targeting_result,
)


def test_resolved_assessment_is_the_only_promotable_target() -> None:
    alternatives = build_targeting_alternatives_from_resolution_artifacts(
        assessments=(
            {
                "assessment_ref": "assessment:1",
                "subject_ref": "subject:1",
                "subject_kind": "entity",
                "right_ref": "snapshot:1",
                "outcome": "resolved",
                "selected_identity_ref": "Q207",
            },
        )
    )
    result = build_targeting_result(claim_id="claim:1", alternatives=alternatives)

    assert result.selection_mode == "resolved"
    assert result.selected_target is not None
    assert result.selected_target.identity_ref == "Q207"
    assert targeting_promotion_allowed(
        targeting_result=result,
        readiness_decision={"outcome": "promote"},
    )


def test_pnf_alternatives_remain_explicitly_ambiguous_and_cannot_promote() -> None:
    alternatives = build_targeting_alternatives_from_resolution_artifacts(
        refinements=(
            {
                "refinement_ref": "refinement:1",
                "partial_pnf_ref": "pnf:1",
                "slot_ref": "subject",
                "retained_alternatives": ["entity:a", "entity:b"],
                "added_alternatives": [],
                "evidence_refs": ["evidence:1"],
            },
        )
    )
    result = build_targeting_result(claim_id="claim:1", alternatives=alternatives)

    assert result.selection_mode == "explicitly_ambiguous"
    assert result.selected_target is None
    assert [row.candidate_ref for row in result.alternatives] == [
        "entity:a",
        "entity:b",
    ]
    assert not targeting_promotion_allowed(
        targeting_result=result,
        readiness_decision={"outcome": "promote"},
    )


def test_multiple_resolved_identities_fail_closed() -> None:
    with pytest.raises(ValueError, match="multiple resolved identities"):
        build_targeting_alternatives_from_resolution_artifacts(
            assessments=(
                {
                    "assessment_ref": "assessment:1",
                    "subject_ref": "subject:1",
                    "subject_kind": "entity",
                    "right_ref": "snapshot:1",
                    "outcome": "resolved",
                    "selected_identity_ref": "Q1",
                },
                {
                    "assessment_ref": "assessment:2",
                    "subject_ref": "subject:1",
                    "subject_kind": "entity",
                    "right_ref": "snapshot:2",
                    "outcome": "resolved",
                    "selected_identity_ref": "Q2",
                },
            )
        )


def test_readiness_hold_blocks_even_a_resolved_target() -> None:
    alternatives = build_targeting_alternatives_from_resolution_artifacts(
        assessments=(
            {
                "assessment_ref": "assessment:1",
                "subject_ref": "subject:1",
                "subject_kind": "entity",
                "right_ref": "snapshot:1",
                "outcome": "resolved",
                "selected_identity_ref": "Q207",
            },
        )
    )
    result = build_targeting_result(claim_id="claim:1", alternatives=alternatives)

    assert not targeting_promotion_allowed(
        targeting_result=result,
        readiness_decision={"outcome": "hold"},
    )


def test_targeting_does_not_require_review_text_or_review_candidate() -> None:
    alternatives = build_targeting_alternatives_from_resolution_artifacts(
        refinements=(
            {
                "refinement_ref": "refinement:1",
                "partial_pnf_ref": "pnf:1",
                "slot_ref": "object",
                "retained_alternatives": ["event:1"],
                "evidence_refs": ["evidence:1"],
            },
        )
    )
    result = build_targeting_result(claim_id="claim:1", alternatives=alternatives)

    assert result.candidate_count == 1
    assert result.selection_mode == "explicitly_ambiguous"
