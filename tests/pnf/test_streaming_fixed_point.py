from __future__ import annotations

import pytest

from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    ConvergentLedger,
    CoverageNotice,
    ObservationDelta,
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
    StreamingDeclaration,
    StreamingSemanticOwner,
    assert_finalising_claim_allowed,
    execute_ready_jobs,
    owner_partition,
)


def _delta(*, document_ref: str = "document:1", sequence_no: int = 0) -> ObservationDelta:
    ref = f"observation:{sequence_no}"
    return ObservationDelta(
        document_ref=document_ref,
        batch_ref=f"batch:{sequence_no}",
        scope_ref=f"sentence:{sequence_no}",
        sequence_no=sequence_no,
        parser_contract="parser:test:v1",
        observation_refs=(ref,),
        observations=(
            {
                "observation_ref": ref,
                "observation_type": "parser.token",
                "token": {"index": sequence_no, "text": "must"},
            },
        ),
        token_start=sequence_no,
        token_end=sequence_no + 1,
        char_start=sequence_no * 5,
        char_end=sequence_no * 5 + 4,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _proposal(job: SolverJob) -> FactorProposal:
    return FactorProposal(
        document_ref=job.owner_key.document_ref,
        source_revision_ref="source-revision:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=(job.owner_key.scope_ref,),
        input_observation_refs=job.input_refs,
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"conduct": job.owner_key.scope_ref},
        qualifier_state={"modality": "obligation"},
        producer_contract="producer:test:v1",
        declaration_revision=job.rule_set_revision,
        candidate_payload={"predicate_ref": "normative.obligation"},
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
        priority=10,
    )


def test_ledger_join_is_associative_commutative_and_idempotent() -> None:
    first = ConvergentLedger(observation_deltas=(_delta(sequence_no=0),))
    second = ConvergentLedger(observation_deltas=(_delta(sequence_no=1),))
    third = ConvergentLedger(observation_deltas=(_delta(sequence_no=2),))

    assert first.join(second).ledger_ref == second.join(first).ledger_ref
    assert first.join(first).ledger_ref == first.ledger_ref
    assert first.join(second).join(third).ledger_ref == first.join(second.join(third)).ledger_ref


def test_multiple_partial_jobs_stream_back_to_one_logical_owner() -> None:
    owner = StreamingSemanticOwner(document_ref="document:1", partition_count=4)
    owner.register_declarations((_declaration(),))
    owner.admit_observation_delta(_delta(sequence_no=0))
    owner.admit_observation_delta(_delta(sequence_no=1))

    before = owner.fixed_point_certificate()
    assert before.pending_jobs == 2
    assert before.local_fixed_point_reached is False

    executor = PythonClosureExecutor(
        {"declaration:test:v1": lambda job: (_proposal(job),)}
    )
    receipts = execute_ready_jobs(owner, executor, workers=2)

    assert len(receipts) == 2
    assert len(owner.ledger.proposals) == 2
    assert owner.fixed_point_certificate().local_fixed_point_reached is True
    assert owner.to_dict()["shared_graph_mutation"] is False
    assert owner.to_dict()["last_writer_wins"] is False


def test_revision_bound_receipt_remains_admissible_when_inputs_still_exist() -> None:
    owner = StreamingSemanticOwner(document_ref="document:1")
    owner.register_declarations((_declaration(),))
    owner.admit_observation_delta(_delta(sequence_no=0))
    job = owner.drain_ready_jobs()[0]
    owner.admit_observation_delta(_delta(sequence_no=1))

    executor = PythonClosureExecutor(
        {"declaration:test:v1": lambda value: (_proposal(value),)}
    )
    receipt = executor.execute(job)
    owner.admit_solver_receipt(receipt)
    owner.reduce_dirty_groups()

    assert receipt.input_revision < owner.revision
    assert receipt.proposals[0].proposal_ref in {
        row.proposal_ref for row in owner.ledger.proposals
    }


def test_finalising_claims_require_coverage_and_fixed_point() -> None:
    owner = StreamingSemanticOwner(document_ref="document:1")
    with pytest.raises(ValueError, match="requires closed"):
        assert_finalising_claim_allowed(
            claim="absence",
            scope_ref="sentence:0",
            barrier="sentence",
            owner=owner,
        )

    owner.admit_coverage_notice(
        CoverageNotice(
            document_ref="document:1",
            scope_ref="sentence:0",
            barrier="sentence",
            state="complete",
            evidence_refs=("parser:receipt",),
        )
    )
    assert_finalising_claim_allowed(
        claim="absence",
        scope_ref="sentence:0",
        barrier="sentence",
        owner=owner,
    )


def test_owner_partition_is_deterministic_and_coordinate_scoped() -> None:
    key = OwnerKey("document:1", "section:4", "semantic.normative_relation")
    assert owner_partition(key, 8) == owner_partition(key, 8)
    assert 0 <= owner_partition(key, 8) < 8


def test_duplicate_proposals_are_idempotent_at_admission() -> None:
    owner = StreamingSemanticOwner(document_ref="document:1")
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.eventuality",
        source_span_refs=("span:1",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="eventuality:v1",
        role_bindings={},
        qualifier_state={},
        producer_contract="producer:base:v1",
        declaration_revision="v1",
        candidate_payload={"predicate": "drive"},
    )
    owner.admit_proposals((proposal, proposal), stage="base")
    owner.reduce_dirty_groups()

    assert len(owner.ledger.proposals) == 1
    assert len(owner.materialized_reduction.factors) == 1
