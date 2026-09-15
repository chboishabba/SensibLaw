from __future__ import annotations

from src.pnf.mabo_slr_profile import (
    EvidenceNeed,
    MaboResidualState,
    build_mabo_slr_profile,
)


def test_exact_common_ground_emits_zero_new_acquisition_requirements() -> None:
    profile = build_mabo_slr_profile(
        consumer_id="mabo:flagship",
        surface_id="mabo:terra-nullius-change",
        residual=MaboResidualState.EXACT,
    )

    assert profile.requirements == ()
    assert profile.evidence_search_authorised is False
    assert profile.world_truth_claimed is False


def test_live_residual_requires_source_identity_authority_and_same_object() -> None:
    profile = build_mabo_slr_profile(
        consumer_id="mabo:flagship",
        surface_id="mabo:terra-nullius-change",
        residual=MaboResidualState.CONTRADICTION,
    )

    assert [requirement.need for requirement in profile.requirements] == [
        EvidenceNeed.SOURCE_IDENTITY,
        EvidenceNeed.SAME_OBJECT,
        EvidenceNeed.AUTHORITY,
    ]
    assert all(requirement.scope == "any" for requirement in profile.requirements)
    assert profile.evidence_search_authorised is True
    assert profile.candidate_only is True
    assert profile.semantic_promotion is False


def test_partial_and_no_typed_meet_remain_distinct_profile_states() -> None:
    partial = build_mabo_slr_profile(
        consumer_id="mabo:flagship",
        surface_id="mabo:terra-nullius-change",
        residual=MaboResidualState.PARTIAL,
    )
    no_meet = build_mabo_slr_profile(
        consumer_id="mabo:flagship",
        surface_id="mabo:terra-nullius-change",
        residual=MaboResidualState.NO_TYPED_MEET,
    )

    assert partial.residual is MaboResidualState.PARTIAL
    assert no_meet.residual is MaboResidualState.NO_TYPED_MEET
    assert partial.requirements == no_meet.requirements
    assert partial.search_reason != no_meet.search_reason


def test_profile_is_only_a_translation_to_existing_slrc_coordinates() -> None:
    profile = build_mabo_slr_profile(
        consumer_id="mabo:flagship",
        surface_id="mabo:terra-nullius-change",
        residual=MaboResidualState.CONTRADICTION,
    )

    assert profile.slrc_version == 2
    assert profile.creates_legal_conclusion is False
    assert profile.creates_evidence_payment is False
    assert profile.requires_review_before_payment is True
    assert profile.python_is_production_slr_semantic_runtime is False
