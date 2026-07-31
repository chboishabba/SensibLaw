from __future__ import annotations

from src.language.annotations import AnnotationLayer, SpanAnnotation
from src.pnf.factor_proposals import FactorProposal
from src.pnf.streaming_fixed_point import (
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
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
