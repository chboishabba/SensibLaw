from __future__ import annotations

from dataclasses import replace

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.pnf.semantic_lifecycle_pipeline import (
    build_admission_aware_semantic_lifecycle,
)


def _proposal(**changes: object) -> FactorProposal:
    base = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=("span:1",),
        input_observation_refs=("observation:must",),
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"bearer": "entity:driver", "conduct": "event:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v1",
        candidate_payload={"predicate_ref": "normative.obligation"},
        fibre_kind="composition",
        support_state="supported",
    )
    return replace(base, **changes)


def test_rejected_alternative_does_not_block_unique_admissible_reading() -> None:
    admitted = _proposal()
    rejected = _proposal(
        role_bindings={"bearer": "entity:owner", "conduct": "event:drive"},
        residuals=("NO_TYPED_MEET",),
    )
    reduction = reduce_factor_proposals(
        document_ref="document:1",
        proposals=(admitted, rejected),
        known_observation_refs=("observation:must",),
    )

    lifecycle = build_admission_aware_semantic_lifecycle(
        document_ref="document:1",
        proposals=(admitted, rejected),
        reduced_factors=reduction.factors,
        reduction_residuals=reduction.residuals,
    )

    admissions = {row.proposal_ref: row.state for row in lifecycle.admissions}
    resolutions = {
        tuple(row.admitted_proposal_refs): row for row in lifecycle.resolutions
    }
    assert admissions[admitted.proposal_ref] == "admitted"
    assert admissions[rejected.proposal_ref] == "rejected"
    assert resolutions[(admitted.proposal_ref,)].state == "resolved_unique"
    assert resolutions[(admitted.proposal_ref,)].selected_proposal_ref == (
        admitted.proposal_ref
    )


def test_blocked_alternative_still_prevents_premature_resolution() -> None:
    admitted = _proposal()
    blocked = _proposal(
        role_bindings={"bearer": "entity:owner", "conduct": "event:drive"},
        coverage_requirements=("axis:actor-role",),
    )
    reduction = reduce_factor_proposals(
        document_ref="document:1",
        proposals=(admitted, blocked),
        known_observation_refs=("observation:must",),
    )

    lifecycle = build_admission_aware_semantic_lifecycle(
        document_ref="document:1",
        proposals=(admitted, blocked),
        reduced_factors=reduction.factors,
        reduction_residuals=reduction.residuals,
    )

    assert all(row.state == "blocked_conflict" for row in lifecycle.resolutions)
    assert all(row.selected_proposal_ref is None for row in lifecycle.resolutions)
