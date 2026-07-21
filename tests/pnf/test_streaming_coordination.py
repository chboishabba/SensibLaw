from __future__ import annotations

from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_coordination import (
    BackpressurePolicy,
    CoordinatedStreamingSemanticOwner,
    HierarchicalDocumentCoordinator,
    SupersessionNotice,
)
from src.pnf.streaming_fixed_point import (
    ObservationDelta,
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
    StreamingDeclaration,
)


def _delta(ref: str, sequence: int) -> ObservationDelta:
    return ObservationDelta(
        document_ref="document:1",
        batch_ref=f"batch:{sequence}",
        scope_ref="sentence:1",
        sequence_no=sequence,
        parser_contract="parser:test:v1",
        observation_refs=(ref,),
        observations=(
            {
                "observation_ref": ref,
                "observation_type": "parser.token",
                "token": {
                    "index": sequence,
                    "text": "must",
                    "lemma": "must",
                },
            },
        ),
        token_start=sequence,
        token_end=sequence + 1,
        char_start=sequence * 5,
        char_end=sequence * 5 + 4,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _declaration() -> StreamingDeclaration:
    return StreamingDeclaration(
        declaration_ref="declaration:test:v1",
        producer_ref="producer:test:v1",
        requires=("parser.token",),
        optional=(),
        emits=("semantic.normative_relation",),
        scope_kind="sentence",
        coverage_barrier="sentence",
        affected_index="semantic.normative_relation",
        declaration_revision="v1",
        priority=1,
    )


def _proposal(job: SolverJob) -> FactorProposal:
    return FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=(job.owner_key.scope_ref,),
        input_observation_refs=job.input_refs,
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"conduct": "event:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="producer:test:v1",
        declaration_revision=job.rule_set_revision,
        candidate_payload={"predicate_ref": "normative.obligation"},
    )


def test_backpressure_defers_without_dropping_parser_delta() -> None:
    owner = CoordinatedStreamingSemanticOwner(
        document_ref="document:1",
        backpressure_policy=BackpressurePolicy(
            max_pending_jobs=1,
            max_in_flight_jobs=2,
            max_dirty_groups=2,
            max_branching_mass=100,
            max_deferred_deltas=2,
            release_batch_size=1,
        ),
    )
    owner.register_declarations((_declaration(),))

    first = owner.offer_observation_delta(_delta("observation:old", 0))
    second = owner.offer_observation_delta(_delta("observation:new", 1))

    assert first.state == "accepted"
    assert second.state == "deferred"
    assert owner.fixed_point_certificate().unconsumed_observation_deltas == 1

    executor = PythonClosureExecutor(
        {"declaration:test:v1": lambda job: (_proposal(job),)}
    )
    jobs = owner.drain_ready_jobs()
    for job in jobs:
        owner.admit_solver_receipt(executor.execute(job))
        owner.reduce_dirty_groups()
    assert owner.release_deferred_deltas() == (second.delta_ref,)


def test_stale_receipt_is_not_admitted_and_is_rescheduled() -> None:
    owner = CoordinatedStreamingSemanticOwner(document_ref="document:1")
    owner.register_declarations((_declaration(),))
    owner.offer_observation_delta(_delta("observation:old", 0))
    old_job = owner.drain_ready_jobs()[0]
    old_receipt = PythonClosureExecutor(
        {"declaration:test:v1": lambda job: (_proposal(job),)}
    ).execute(old_job)

    owner.admit_supersession_notice(
        SupersessionNotice(
            document_ref="document:1",
            replacement_pairs=(("observation:old", "observation:new"),),
            reason_ref="parser-correction:1",
        )
    )
    stale_delta = owner.admit_solver_receipt(old_receipt)

    assert old_receipt.proposals[0].proposal_ref not in {
        row.proposal_ref for row in owner.ledger.proposals
    }
    assert stale_delta.introduced_residual_refs
    assert owner.fixed_point_certificate().pending_jobs == 1

    owner.offer_observation_delta(_delta("observation:new", 1))
    replacement_jobs = owner.drain_ready_jobs()
    assert replacement_jobs
    assert all(
        "observation:new" in job.input_refs for job in replacement_jobs
    )


def test_supersession_retracts_materialized_proposals() -> None:
    owner = CoordinatedStreamingSemanticOwner(document_ref="document:1")
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.eventuality",
        source_span_refs=("sentence:1",),
        input_observation_refs=("observation:old",),
        dependency_factor_refs=(),
        structural_signature="eventuality:v1",
        role_bindings={},
        qualifier_state={},
        producer_contract="producer:base:v1",
        declaration_revision="v1",
        candidate_payload={"predicate": "drive"},
    )
    owner._observation_refs.add("observation:old")
    owner.admit_proposals((proposal,), stage="base")
    owner.reduce_dirty_groups()
    assert owner.materialized_reduction.factors

    owner.admit_supersession_notice(
        SupersessionNotice(
            document_ref="document:1",
            replacement_pairs=(("observation:old", "observation:new"),),
            reason_ref="parser-correction:1",
        )
    )
    owner.reduce_dirty_groups()

    assert owner.materialized_reduction.factors == ()
    assert proposal.proposal_ref in owner.coordination_to_dict()[
        "retracted_proposal_refs"
    ]


def test_hierarchical_coordinator_waits_for_boundary_discharge() -> None:
    first = CoordinatedStreamingSemanticOwner(document_ref="document:1")
    second = CoordinatedStreamingSemanticOwner(document_ref="document:1")
    first._observation_deltas.clear()
    second._observation_deltas.clear()
    coordinator = HierarchicalDocumentCoordinator(document_ref="document:1")
    coordinator.register_region(
        summary=first.region_boundary_summary("section:1"),
        certificate=first.fixed_point_certificate(),
    )
    coordinator.register_region(
        summary=second.region_boundary_summary("section:2"),
        certificate=second.fixed_point_certificate(),
    )
    coordinator.route_boundary_obligation(
        obligation_ref="boundary:definition:1",
        target_scope_ref="section:2",
    )

    assert coordinator.local_fixed_point_reached is False
    coordinator.discharge_boundary_obligation("boundary:definition:1")
    assert coordinator.local_fixed_point_reached is True
    assert coordinator.to_dict()["identity_promoted"] is False
