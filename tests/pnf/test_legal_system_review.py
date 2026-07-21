from __future__ import annotations

from src.pnf.legal_system_review import (
    create_review_claim,
    create_system_review_attestation,
    project_system_review,
)


def test_lawyer_can_review_identification_placement_function_outcome_and_implication() -> None:
    claims = (
        create_review_claim(
            claim_kind="identification",
            subject_ref="legal-node:section-5",
            proposition_ref="proposition:correct-law-identified",
            target_refs=("source:act-2020-s5",),
            source_span_refs=("span:s5",),
        ),
        create_review_claim(
            claim_kind="graph_placement",
            subject_ref="legal-node:section-5",
            proposition_ref="proposition:correctly-under-parent-rule",
            target_refs=("legal-node:part-2",),
        ),
        create_review_claim(
            claim_kind="legal_function",
            subject_ref="legal-node:section-5",
            proposition_ref="proposition:function-is-prohibition",
        ),
        create_review_claim(
            claim_kind="legal_outcome",
            subject_ref="legal-node:section-5",
            proposition_ref="proposition:breach-enables-penalty-path",
        ),
        create_review_claim(
            claim_kind="legal_implication",
            subject_ref="legal-node:section-5",
            proposition_ref="proposition:licence-exception-defeats-base-application",
            residual_refs=("burden_allocation_unresolved",),
        ),
    )
    states = {
        claims[0].claim_ref: "supported",
        claims[1].claim_ref: "supported",
        claims[2].claim_ref: "supported",
        claims[3].claim_ref: "supported_with_residuals",
        claims[4].claim_ref: "supported_with_residuals",
    }
    attestation = create_system_review_attestation(
        revision_ref="revision:legal-subgraph-1",
        build_ref="legal-semantic-build:1",
        reviewer_ref="lawyer:alice",
        credential_refs=("credential:qld-solicitor",),
        institution_ref="firm:example",
        review_state="approve_with_residuals",
        claim_states=states,
        reason_refs=("reason:source-and-doctrine-checked",),
        evidence_refs=("source:act-2020", "case:example"),
        method_refs=("method:manual-legal-review",),
        created_at="2026-07-21T12:00:00Z",
    )

    projection = project_system_review(
        revision_ref="revision:legal-subgraph-1",
        build_ref="legal-semantic-build:1",
        attestations=(attestation,),
        accepted_credential_refs=("credential:qld-solicitor",),
    )

    assert projection.state == "supported_with_residuals_in_scope"
    assert set(projection.supported_claim_refs) == {claims[0].claim_ref, claims[1].claim_ref, claims[2].claim_ref}
    assert set(projection.qualified_claim_refs) == {claims[3].claim_ref, claims[4].claim_ref}
    assert projection.to_dict()["truth_closed"] is False


def test_conflicting_system_reviews_preserve_contestation() -> None:
    claim = create_review_claim(
        claim_kind="reconstruction_fitness",
        subject_ref="legal-subgraph:1",
        proposition_ref="proposition:itir-reconstruction-is-fit-for-use",
    )
    common = {
        "revision_ref": "revision:1",
        "build_ref": "build:1",
        "credential_refs": ("credential:lawyer",),
        "institution_ref": None,
        "review_state": "endorse",
        "reason_refs": (),
        "evidence_refs": (),
        "method_refs": ("method:manual-review",),
        "created_at": "2026-07-21T12:00:00Z",
    }
    yes = create_system_review_attestation(
        reviewer_ref="lawyer:a",
        claim_states={claim.claim_ref: "supported"},
        **common,
    )
    no = create_system_review_attestation(
        reviewer_ref="lawyer:b",
        claim_states={claim.claim_ref: "unsupported"},
        **common,
    )

    projection = project_system_review(
        revision_ref="revision:1",
        build_ref="build:1",
        attestations=(yes, no),
    )

    assert projection.state == "contested_in_scope"
    assert projection.contested_claim_refs == (claim.claim_ref,)
    assert projection.to_dict()["universal_authority"] is False
