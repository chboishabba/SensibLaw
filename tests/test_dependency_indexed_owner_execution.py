from __future__ import annotations

from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.policy.dependency_indexed_owner_execution import (
    install_dependency_indexed_owner_execution,
)


def _proposal(
    *,
    scope: str,
    family: str,
    ordinal: int,
    dependencies: tuple[str, ...] = (),
) -> FactorProposal:
    return FactorProposal(
        document_ref="document:test",
        source_revision_ref="source:test",
        factor_type_ref=family,
        source_span_refs=(scope,),
        input_observation_refs=(),
        dependency_factor_refs=dependencies,
        structural_signature=f"signature:{family}",
        role_bindings={"role": f"value:{ordinal}"},
        qualifier_state={},
        producer_contract="producer:test",
        declaration_revision="v1",
        candidate_payload={"ordinal": ordinal},
        scope_ref=scope,
    )


def _factor_ref(proposal: FactorProposal) -> str:
    reduction = reduce_factor_proposals(
        document_ref="document:test",
        proposals=(proposal,),
    )
    assert len(reduction.factors) == 1
    return reduction.factors[0].factor_ref


def test_dependency_availability_wakes_only_indexed_successor_owner() -> None:
    install_dependency_indexed_owner_execution()
    owner = BoundedStreamingSemanticOwner(document_ref="document:test")

    # Sort the dependent owner before the producer owner. Its first reduction
    # therefore sees no available dependency and must remain outside factors.
    producer = _proposal(
        scope="scope:z-producer",
        family="semantic.producer",
        ordinal=1,
    )
    producer_ref = _factor_ref(producer)
    dependent = _proposal(
        scope="scope:a-dependent",
        family="semantic.dependent",
        ordinal=2,
        dependencies=(producer_ref,),
    )

    owner.admit_proposals((dependent, producer), stage="base")
    owner.reduce_dirty_groups()

    factors = owner.materialized_reduction.factors
    factor_types = {factor.factor_type_ref for factor in factors}
    assert factor_types == {"semantic.producer", "semantic.dependent"}

    telemetry = owner.kernel_telemetry()["counts"]
    assert telemetry["dependency_reverse_edges_indexed"] == 1
    assert telemetry["dependency_indexed_owner_wakeups"] >= 1
    assert telemetry["dependency_reduction_steps"] >= 3


def test_empty_dependency_authority_is_not_treated_as_validation_disabled() -> None:
    install_dependency_indexed_owner_execution()
    owner = BoundedStreamingSemanticOwner(document_ref="document:test")
    dependent = _proposal(
        scope="scope:a-dependent",
        family="semantic.dependent",
        ordinal=1,
        dependencies=("factor:missing",),
    )

    owner.admit_proposals((dependent,), stage="base")
    owner.reduce_dirty_groups()

    assert owner.materialized_reduction.factors == ()
    assert any(
        residual.residual_type == "missing_reduction_input"
        for residual in owner.materialized_reduction.residuals
    )
