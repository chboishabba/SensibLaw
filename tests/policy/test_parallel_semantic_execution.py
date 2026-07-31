from __future__ import annotations

import multiprocessing

import pytest

from src.language.annotations import AnnotationLayer, SpanAnnotation
from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    ObservationDelta,
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
    StreamingDeclaration,
    StreamingSemanticOwner,
)
from src.policy import corpus_compilation as legacy
from src.policy import operational_corpus_compilation as operational
from src.policy.parallel_semantic_execution import (
    SemanticExecutionContext,
    _ACTIVE_CONTEXTS,
    _ACTIVE_LOCK,
    _solver_receipt_from_row,
    indexed_atom_mention_refs,
    indexed_parser_observation_refs_by_mention,
    prepare_closure_activation_leaves,
)


def _semantic_layer() -> AnnotationLayer:
    return AnnotationLayer(
        layer_ref="layer:semantic-test",
        tokenizer_ref="parser:test",
        text_sha256="text-sha",
        span_annotations=(
            SpanAnnotation("parser:0", 0, 1, "parser_token", {}),
            SpanAnnotation("parser:1", 1, 2, "parser_token", {}),
            SpanAnnotation("parser:2", 2, 3, "parser_token", {}),
            SpanAnnotation("parser:3", 3, 4, "parser_token", {}),
            SpanAnnotation("atom-span:1", 0, 2, "semantic_atom", {}),
            SpanAnnotation("atom-span:2", 2, 4, "semantic_atom", {}),
        ),
    )


def _mentions() -> tuple[dict[str, object], ...]:
    return (
        {"mention_ref": "mention:1", "start_token": 0, "end_token": 1},
        {"mention_ref": "mention:2", "start_token": 1, "end_token": 3},
        {"mention_ref": "mention:3", "start_token": 3, "end_token": 4},
    )


def _solver_job() -> SolverJob:
    return SolverJob(
        owner_key=OwnerKey("document:1", "sentence:1", "semantic.test"),
        declaration_ref="declaration:test",
        input_revision=3,
        input_refs=("observation:1",),
        input_payload={"observations": []},
        rule_set_revision="v1",
        coverage_requirements=("coverage:1",),
    )


def _proposal(value: SolverJob) -> FactorProposal:
    return FactorProposal(
        document_ref=value.owner_key.document_ref,
        source_revision_ref="source:1",
        factor_type_ref="semantic.test",
        source_span_refs=(value.owner_key.scope_ref,),
        input_observation_refs=value.input_refs,
        dependency_factor_refs=(),
        structural_signature="signature:test",
        role_bindings={},
        qualifier_state={},
        producer_contract="producer:test",
        declaration_revision=value.rule_set_revision,
        candidate_payload={"value": "candidate"},
    )


def _activation_delta(sequence_no: int) -> ObservationDelta:
    return ObservationDelta(
        document_ref="document:activation",
        batch_ref=f"batch:{sequence_no}",
        scope_ref=f"sentence:{sequence_no}",
        sequence_no=sequence_no,
        parser_contract="parser:test",
        observation_refs=(f"observation:{sequence_no}",),
        observations=(
            {
                "observation_ref": f"observation:{sequence_no}",
                "observation_type": "parser.token",
                "token": {"index": sequence_no, "text": "must"},
            },
        ),
        token_start=sequence_no,
        token_end=sequence_no + 1,
        char_start=sequence_no,
        char_end=sequence_no + 1,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _activation_declaration() -> StreamingDeclaration:
    return StreamingDeclaration(
        declaration_ref="declaration:activation",
        producer_ref="producer:activation",
        requires=("parser.token",),
        optional=(),
        emits=("semantic.activation",),
        scope_kind="sentence",
        coverage_barrier="sentence",
        affected_index="semantic.activation",
        declaration_revision="v1",
        priority=1,
    )


def _activation_context(tmp_path, leaf_size: int) -> SemanticExecutionContext:
    return SemanticExecutionContext(
        document_ref="document:activation",
        source_sha256="source-sha",
        parser_contract_ref="parser:test",
        build_key_sha256="build-key",
        typing_workers=1,
        leaf_capacity=4,
        hierarchy_arity=2,
        checkpoint_root=tmp_path,
        resource_ledger=None,
        run_ref="semantic-execution:activation",
        closure_activation_leaf_size=leaf_size,
    )


def test_parallel_semantic_strategy_is_installed_after_bounded_closure() -> None:
    assert getattr(operational, "_parallel_semantic_execution_installed", False)
    assert hasattr(operational, "_bounded_streaming_semantic_build")
    assert hasattr(operational, "_canonical_compile_document_operational")
    assert hasattr(legacy, "_serial_atom_mention_refs")
    assert hasattr(legacy, "_serial_parser_observation_refs_by_mention")


def test_indexed_atom_mention_matching_preserves_canonical_output() -> None:
    layer = _semantic_layer()
    atom_span_refs = {"atom:1": "atom-span:1", "atom:2": "atom-span:2"}
    mentions = _mentions()

    serial = legacy._serial_atom_mention_refs(
        semantic_layer=layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )
    indexed = indexed_atom_mention_refs(
        semantic_layer=layer,
        atom_span_refs=atom_span_refs,
        mentions=mentions,
    )

    assert indexed == serial == {
        "atom:1": ("mention:1", "mention:2"),
        "atom:2": ("mention:2", "mention:3"),
    }


def test_indexed_parser_observation_matching_preserves_canonical_output() -> None:
    layer = _semantic_layer()
    mentions = _mentions()

    serial = legacy._serial_parser_observation_refs_by_mention(
        semantic_layer=layer,
        mentions=mentions,
    )
    indexed = indexed_parser_observation_refs_by_mention(
        semantic_layer=layer,
        mentions=mentions,
    )

    assert indexed == serial == {
        "mention:1": ("parser:0",),
        "mention:2": ("parser:1", "parser:2"),
        "mention:3": ("parser:3",),
    }


def test_solver_receipt_round_trip_preserves_content_identity() -> None:
    job = _solver_job()

    def solve(value: SolverJob) -> tuple[FactorProposal, ...]:
        return (_proposal(value),)

    receipt = PythonClosureExecutor({"declaration:test": solve}).execute(job)
    replayed = _solver_receipt_from_row(receipt.to_dict())

    assert replayed.receipt_ref == receipt.receipt_ref
    assert replayed.proposals[0].proposal_ref == receipt.proposals[0].proposal_ref
    assert replayed.to_dict() == receipt.to_dict()


def test_second_closure_execution_replays_checkpoint_without_solver(tmp_path) -> None:
    job = _solver_job()
    calls = 0

    def solve(value: SolverJob) -> tuple[FactorProposal, ...]:
        nonlocal calls
        calls += 1
        return (_proposal(value),)

    context = SemanticExecutionContext(
        document_ref=job.owner_key.document_ref,
        source_sha256="source-sha",
        parser_contract_ref="parser:test",
        build_key_sha256="build-key",
        typing_workers=1,
        leaf_capacity=4,
        hierarchy_arity=2,
        checkpoint_root=tmp_path,
        resource_ledger=None,
        run_ref="semantic-execution:closure-replay",
    )
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        executor = PythonClosureExecutor({"declaration:test": solve})
        first = executor.execute(job)
        second = executor.execute(job)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)

    assert first.receipt_ref == second.receipt_ref
    assert calls == 1
    assert context.closure_counters["receipts_computed"] == 1
    assert context.closure_counters["receipts_reused"] == 1
    checkpoint = context.closure_receipt_path(job.job_ref)
    assert checkpoint is not None and checkpoint.exists()


def test_closure_activation_leaves_preserve_canonical_admission_and_job_identity(
    tmp_path,
) -> None:
    deltas = tuple(reversed(tuple(_activation_delta(index) for index in range(6))))
    results = []
    for leaf_size in (1, 2, 64):
        context = _activation_context(tmp_path / str(leaf_size), leaf_size)
        prepared = prepare_closure_activation_leaves(
            context=context, observation_deltas=deltas
        )
        owner = StreamingSemanticOwner(document_ref="document:activation")
        owner.register_declarations((_activation_declaration(),))
        for delta in prepared:
            owner.admit_observation_delta(delta)
        jobs = owner.drain_ready_jobs()
        executor = PythonClosureExecutor(
            {"declaration:activation": lambda job: (_proposal(job),)}
        )
        for job in jobs:
            owner.admit_solver_receipt(executor.execute(job))
            owner.reduce_dirty_groups()
        results.append(
            (
                tuple(delta.delta_ref for delta in prepared),
                tuple(job.job_ref for job in jobs),
                tuple(row.receipt_ref for row in owner.ledger.receipts),
                owner.fixed_point_certificate().certificate_ref,
                owner.to_dict()["ledger"],
            )
        )
        assert context.closure_activation["leaf_count"] == (6 + leaf_size - 1) // leaf_size
    assert results[0] == results[1] == results[2]


def test_closure_activation_leaves_restart_without_additional_worker_computation(
    tmp_path,
) -> None:
    deltas = tuple(_activation_delta(index) for index in range(3))
    first = _activation_context(tmp_path, 1)
    second = _activation_context(tmp_path, 1)
    assert prepare_closure_activation_leaves(context=first, observation_deltas=deltas)
    assert prepare_closure_activation_leaves(context=second, observation_deltas=deltas)
    assert first.closure_activation["computed_leaf_count"] == 3
    assert second.closure_activation["computed_leaf_count"] == 0
    assert second.closure_activation["reused_leaf_count"] == 3


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="process-backed activation preflight requires fork on this platform",
)
def test_process_backed_closure_activation_is_a_parallel_preflight_gate(
    monkeypatch, tmp_path
) -> None:
    from src.policy.parallel_typing_tail import shutdown_semantic_process_pool

    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "2")
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_MP_CONTEXT", "fork")
    context = _activation_context(tmp_path, 1)
    deltas = tuple(_activation_delta(index) for index in range(16))
    try:
        prepared = prepare_closure_activation_leaves(
            context=context, observation_deltas=deltas
        )
    finally:
        shutdown_semantic_process_pool()

    owner = StreamingSemanticOwner(document_ref="document:activation")
    owner.register_declarations((_activation_declaration(),))
    for delta in prepared:
        owner.admit_observation_delta(delta)
    jobs = owner.drain_ready_jobs()
    executor = PythonClosureExecutor(
        {"declaration:activation": lambda job: (_proposal(job),)}
    )
    for job in jobs:
        owner.admit_solver_receipt(executor.execute(job))
        owner.reduce_dirty_groups()
    assert len(jobs) == len(deltas)
    assert len(owner.ledger.receipts) == len(deltas)
    assert owner.fixed_point_certificate().local_fixed_point_reached is True
    assert len(context.closure_activation["worker_pids"]) >= 2
