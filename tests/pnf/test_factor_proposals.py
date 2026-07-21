from __future__ import annotations

from src.pnf.factor_proposals import (
    CrossDocumentRelation,
    FactorProposal,
    proposal_build_key,
    reduce_factor_proposals,
)


def _proposal(*, bearer: str, payload: str = "drive") -> FactorProposal:
    return FactorProposal(
        document_ref="document:qld-road-rules",
        source_revision_ref="source-revision:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=("span:1",),
        input_observation_refs=("observation:must", "observation:drive"),
        dependency_factor_refs=(),
        structural_signature="signature:normative-operation:v1",
        role_bindings={"bearer": bearer, "conduct": "eventuality:drive"},
        qualifier_state={"modality": "obligation", "polarity": "positive"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v0_1",
        candidate_payload={"predicate_ref": payload},
        residuals=("jurisdiction_unresolved",),
    )


def test_reducer_is_order_independent_and_deduplicates_exact_proposals() -> None:
    first = _proposal(bearer="entity:driver")
    duplicate = _proposal(bearer="entity:driver")
    left = reduce_factor_proposals(
        document_ref=first.document_ref,
        proposals=(first, duplicate),
        known_observation_refs=("observation:must", "observation:drive"),
    )
    right = reduce_factor_proposals(
        document_ref=first.document_ref,
        proposals=(duplicate, first),
        known_observation_refs=("observation:drive", "observation:must"),
    )

    assert left.graph_ref == right.graph_ref
    assert left.deduplicated_count == 1
    assert len(left.factors) == 1
    assert left.factors[0].proposal_refs == (first.proposal_ref,)
    assert left.to_dict()["legal_truth_closed"] is False


def test_incompatible_coordinates_remain_explicit_alternatives() -> None:
    driver = _proposal(bearer="entity:driver")
    owner = _proposal(bearer="entity:owner")
    reduction = reduce_factor_proposals(
        document_ref=driver.document_ref,
        proposals=(owner, driver),
        known_observation_refs=("observation:must", "observation:drive"),
    )

    assert len(reduction.factors) == 2
    assert [row.residual_type for row in reduction.residuals] == ["incompatible_alternatives"]
    assert set(reduction.residuals[0].proposal_refs) == {driver.proposal_ref, owner.proposal_ref}


def test_missing_declared_inputs_do_not_race_into_graph() -> None:
    proposal = _proposal(bearer="entity:driver")
    reduction = reduce_factor_proposals(
        document_ref=proposal.document_ref,
        proposals=(proposal,),
        known_observation_refs=("observation:must",),
    )

    assert reduction.factors == ()
    assert reduction.residuals[0].residual_type == "missing_reduction_input"


def test_build_key_targets_only_declared_inputs() -> None:
    first = proposal_build_key(
        canonical_text_digest="text:1",
        producer_contract="producer:1",
        declaration_revision="v1",
        input_observation_digests=("b", "a"),
        dependency_factor_digests=("d", "c"),
    )
    second = proposal_build_key(
        canonical_text_digest="text:1",
        producer_contract="producer:1",
        declaration_revision="v1",
        input_observation_digests=("a", "b"),
        dependency_factor_digests=("c", "d"),
    )
    assert first == second


def test_cross_document_relation_never_closes_identity() -> None:
    relation = CrossDocumentRelation(
        relation_type="AmendmentRelation",
        source_document_ref="document:amending-act",
        target_document_ref="document:principal-act",
        source_coordinate_refs=("span:source",),
        target_coordinate_refs=("section:45",),
        evidence_refs=("observation:amends",),
        residuals=("effective_time_unresolved",),
    )
    payload = relation.to_dict()
    assert payload["identity_closed"] is False
    assert payload["legal_conclusion_promoted"] is False
