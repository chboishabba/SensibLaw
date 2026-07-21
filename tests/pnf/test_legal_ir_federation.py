from __future__ import annotations

from src.pnf.legal_ir_federation import (
    ReviewerCredential,
    build_federation_bundle,
    create_graph_revision,
    create_review_attestation,
    project_federated_claim_state,
)


def test_reviews_preserve_disagreement_and_never_close_truth() -> None:
    revision = create_graph_revision(
        subject_ref="legal-ir:claim:1",
        payload={"predicate": "normative.prohibition"},
        source_span_refs=("span:1",),
        legal_system_refs=("AU.COMMON",),
        jurisdiction_refs=("AU",),
        author_ref="lawyer:alice",
        institution_ref="firm:a",
        build_ref="legal-semantic-build:1",
    )
    endorse = create_review_attestation(
        revision_ref=revision.revision_ref,
        reviewer_ref="lawyer:bob",
        credential_refs=("credential:bob",),
        institution_ref="firm:b",
        review_state="endorse",
        coordinate_states={"modality": "satisfied", "exception": "unresolved"},
        reason_refs=("reason:source-aligned",),
        evidence_refs=("span:1",),
        supersedes_attestation_refs=(),
        created_at="2026-07-21T00:00:00Z",
    )
    reject = create_review_attestation(
        revision_ref=revision.revision_ref,
        reviewer_ref="lawyer:carol",
        credential_refs=("credential:carol",),
        institution_ref="firm:c",
        review_state="reject",
        coordinate_states={"modality": "contested"},
        reason_refs=("reason:scope-wrong",),
        evidence_refs=("span:1",),
        supersedes_attestation_refs=(),
        created_at="2026-07-21T01:00:00Z",
    )
    projection = project_federated_claim_state(
        revision_ref=revision.revision_ref,
        attestations=(endorse, reject),
    )
    assert projection.state == "contested"
    assert projection.endorsement_count == 1
    assert projection.rejection_count == 1
    assert projection.to_dict()["truth_closed"] is False
    assert "exception" in projection.unresolved_coordinate_refs


def test_superseded_reviews_stop_counting_and_scope_can_filter() -> None:
    revision = create_graph_revision(
        subject_ref="legal-ir:claim:2",
        payload={"predicate": "judicial.holding"},
        author_ref="lawyer:a",
        institution_ref="court:registry",
        build_ref="build:2",
    )
    old = create_review_attestation(
        revision_ref=revision.revision_ref,
        reviewer_ref="lawyer:b",
        credential_refs=("credential:b",),
        institution_ref="firm:b",
        review_state="reject",
        coordinate_states={},
        reason_refs=(),
        evidence_refs=(),
        supersedes_attestation_refs=(),
        created_at="2026-07-21T00:00:00Z",
    )
    replacement = create_review_attestation(
        revision_ref=revision.revision_ref,
        reviewer_ref="lawyer:b",
        credential_refs=("credential:b",),
        institution_ref="firm:b",
        review_state="endorse",
        coordinate_states={},
        reason_refs=(),
        evidence_refs=(),
        supersedes_attestation_refs=(old.attestation_ref,),
        created_at="2026-07-21T02:00:00Z",
    )
    projection = project_federated_claim_state(
        revision_ref=revision.revision_ref,
        attestations=(old, replacement),
        accepted_institution_refs=("firm:b",),
        scope_ref="scope:firm-b",
    )
    assert projection.endorsement_count == 1
    assert projection.rejection_count == 0
    assert projection.state == "endorsed_in_scope"

    credential = ReviewerCredential(
        credential_ref="credential:b",
        reviewer_ref="lawyer:b",
        institution_ref="firm:b",
        jurisdiction_refs=("AU",),
        practice_area_refs=("administrative-law",),
        credential_type_refs=("admitted-solicitor",),
        valid_from="2020-01-01",
        valid_until=None,
        evidence_refs=("registry:admissions",),
        verification_state="verified_candidate",
    )
    bundle = build_federation_bundle(
        revisions=(revision,),
        credentials=(credential,),
        attestations=(old, replacement),
        projections=(projection,),
        federation_refs=("federation:au-public-law",),
    )
    payload = bundle.to_dict()
    assert payload["disagreement_preserved"] is True
    assert payload["anonymous_consensus"] is False
