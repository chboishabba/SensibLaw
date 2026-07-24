from __future__ import annotations

from dataclasses import replace

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.pnf.semantic_lifecycle import build_semantic_lifecycle


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


def _reduction(*proposals: FactorProposal):
    return reduce_factor_proposals(
        document_ref="document:1",
        proposals=proposals,
        known_observation_refs=("observation:must",),
    )


def test_supported_candidate_is_admitted_and_resolved_unique() -> None:
    proposal = _proposal()
    reduction = _reduction(proposal)
    lifecycle = build_semantic_lifecycle(
        document_ref="document:1",
        proposals=(proposal,),
        reduced_factors=reduction.factors,
    )

    assert lifecycle.assessments[0].outcome == "satisfied"
    assert lifecycle.admissions[0].state == "admitted"
    assert lifecycle.resolutions[0].state == "resolved_unique"
    assert lifecycle.resolutions[0].selected_proposal_ref == proposal.proposal_ref
    assert lifecycle.to_dict()["reduction_is_not_resolution"] is True
    assert lifecycle.to_dict()["memory_transition_performed"] is False


def test_undetermined_coverage_is_blocked_not_rejected() -> None:
    proposal = _proposal(coverage_requirements=("axis:bfo",))
    reduction = _reduction(proposal)
    lifecycle = build_semantic_lifecycle(
        document_ref="document:1",
        proposals=(proposal,),
        reduced_factors=reduction.factors,
    )

    assert lifecycle.assessments[0].outcome == "undetermined"
    assert lifecycle.admissions[0].state == "blocked"
    assert lifecycle.admissions[0].invalidation_grounds == ()
    assert lifecycle.resolutions[0].state == "blocked_insufficient_coverage"


def test_support_and_contradiction_remain_both_and_block_resolution() -> None:
    proposal = _proposal()
    reduction = _reduction(proposal)
    fibre_elements = (
        {
            "element_ref": "element:support",
            "coordinate_ref": proposal.semantic_coordinate_ref,
            "derivation_role": "support",
            "source_refs": ("span:1",),
        },
        {
            "element_ref": "element:contradict",
            "coordinate_ref": proposal.semantic_coordinate_ref,
            "derivation_role": "contradict",
            "source_refs": ("evidence:counterexample",),
        },
    )
    lifecycle = build_semantic_lifecycle(
        document_ref="document:1",
        proposals=(proposal,),
        reduced_factors=reduction.factors,
        fibre_elements=fibre_elements,
    )

    assert lifecycle.assessments[0].outcome == "both"
    assert lifecycle.admissions[0].state == "blocked"
    assert lifecycle.resolutions[0].state == "blocked_conflict"
    assert lifecycle.resolutions[0].selected_proposal_ref is None


def test_positive_invalidation_rejects_candidate() -> None:
    proposal = _proposal(residuals=("NO_TYPED_MEET",))
    reduction = _reduction(proposal)
    lifecycle = build_semantic_lifecycle(
        document_ref="document:1",
        proposals=(proposal,),
        reduced_factors=reduction.factors,
    )

    assert lifecycle.assessments[0].outcome == "violated"
    assert "failed_typed_meet" in lifecycle.assessments[0].invalidation_grounds
    assert lifecycle.admissions[0].state == "rejected"
    assert lifecycle.resolutions[0].state == "blocked_conflict"
