from __future__ import annotations

from src.pnf.review_coordinates import (
    SemanticReviewAssessment,
    SemanticReviewCoordinate,
    project_review_state,
)


def test_review_coordinates_link_proposal_factor_relation_and_build_without_promotion() -> None:
    coordinate = SemanticReviewCoordinate(
        target_kind="cross_document_relation",
        target_ref="cross-document-relation:amendment",
        document_refs=("document:amending", "document:principal"),
        coordinate_refs=("span:amends", "section:45"),
        review_dimension="temporal_validity",
        residuals=("effective_time_unresolved",),
    )
    payload = coordinate.to_dict()
    assert payload["semantic_state_mutated"] is False
    assert payload["document_refs"] == ["document:amending", "document:principal"]


def test_conflicting_scoped_assessments_remain_contested() -> None:
    coordinate = SemanticReviewCoordinate(
        target_kind="reduced_factor",
        target_ref="factor:prohibition",
        document_refs=("document:qld-road-rules",),
        coordinate_refs=("span:must-not-drive",),
        review_dimension="legal_function",
    )
    supported = SemanticReviewAssessment(
        coordinate_ref=coordinate.coordinate_ref,
        reviewer_credential_ref="credential:one",
        institution_ref="institution:qld-a",
        review_state="supported",
        rationale_refs=("note:1",),
    )
    unsupported = SemanticReviewAssessment(
        coordinate_ref=coordinate.coordinate_ref,
        reviewer_credential_ref="credential:two",
        institution_ref="institution:qld-b",
        review_state="unsupported",
        rationale_refs=("note:2",),
    )
    projection = project_review_state(
        coordinate=coordinate,
        assessments=(unsupported, supported),
    )
    assert projection["contested"] is True
    assert projection["truth_closed"] is False
    assert projection["semantic_state_promoted"] is False


def test_credential_scope_does_not_create_universal_authority() -> None:
    coordinate = SemanticReviewCoordinate(
        target_kind="semantic_build",
        target_ref="legal-semantic-build:1",
        document_refs=("document:1",),
        coordinate_refs=(),
        review_dimension="build_fitness",
    )
    assessment = SemanticReviewAssessment(
        coordinate_ref=coordinate.coordinate_ref,
        reviewer_credential_ref="credential:accepted",
        institution_ref="institution:accepted",
        review_state="supported_with_residuals",
        rationale_refs=("note:qualified",),
        residuals=("jurisdiction_unresolved",),
    )
    hidden = project_review_state(
        coordinate=coordinate,
        assessments=(assessment,),
        accepted_credential_refs=("credential:other",),
    )
    visible = project_review_state(
        coordinate=coordinate,
        assessments=(assessment,),
        accepted_credential_refs=("credential:accepted",),
    )
    assert hidden["assessment_refs"] == []
    assert visible["states"] == ["supported_with_residuals"]
