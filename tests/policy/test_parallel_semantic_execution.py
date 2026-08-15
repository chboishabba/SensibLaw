from __future__ import annotations

import multiprocessing
import shutil

import pytest

from src.language.annotations import AnnotationLayer, SpanAnnotation
from src.pnf.factor_proposals import FactorProposal
from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner
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
from src.policy.carriers.canonical import canonical_sha256
from src.policy.parallel_semantic_execution import (
    CLOSURE_ACTIVATION_CONTRACT,
    CLOSURE_HANDOFF_CONTRACT,
    CLOSURE_HANDOFF_SCHEMA_VERSION,
    CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION,
    ClosureOwnerReplayContract,
    SemanticExecutionContext,
    _ACTIVE_CONTEXTS,
    _ACTIVE_LOCK,
    _CONTEXT,
    _atomic_write_json,
    _read_json,
    _solver_receipt_from_row,
    _replay_artifact_path,
    _write_replay_artifact,
    indexed_atom_mention_refs,
    indexed_parser_observation_refs_by_mention,
    prepare_closure_activation_leaves,
)
from src.runtime.stage_timing import StageTimingLedger


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

    assert (
        indexed
        == serial
        == {
            "atom:1": ("mention:1", "mention:2"),
            "atom:2": ("mention:2", "mention:3"),
        }
    )


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

    assert (
        indexed
        == serial
        == {
            "mention:1": ("parser:0",),
            "mention:2": ("parser:1", "parser:2"),
            "mention:3": ("parser:3",),
        }
    )


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
    deltas = tuple(reversed(tuple(_activation_delta(index) for index in range(513))))
    results = []
    for leaf_size in (256, 512, 4096):
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
        assert prepared == tuple(
            sorted(deltas, key=lambda delta: (delta.sequence_no, delta.delta_ref))
        )
        assert all(any(delta is original for original in deltas) for delta in prepared)
        assert (
            context.closure_activation["leaf_count"]
            == (513 + leaf_size - 1) // leaf_size
        )
        assert (
            context.closure_activation["max_buffered_leaves"]
            <= context.closure_activation["buffer_limit_leaves"]
        )
        assert (
            len(context.closure_activation["admitted_leaf_refs"])
            == (513 + leaf_size - 1) // leaf_size
        )
    assert results[0] == results[1] == results[2]


def test_closure_activation_leaves_restart_without_additional_worker_computation(
    monkeypatch,
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
    monkeypatch.setattr(
        ObservationDelta,
        "to_dict",
        lambda _self: (_ for _ in ()).throw(
            AssertionError("parent rematerialized delta")
        ),
    )
    reused = prepare_closure_activation_leaves(
        context=_activation_context(tmp_path, 1), observation_deltas=deltas
    )
    assert reused == deltas


def test_activation_admission_telemetry_starts_after_leaf_completion(tmp_path) -> None:
    context = _activation_context(tmp_path, 2)
    deltas = tuple(_activation_delta(index) for index in range(4))
    prepared = prepare_closure_activation_leaves(
        context=context, observation_deltas=deltas
    )
    owner = BoundedStreamingSemanticOwner(document_ref="document:activation")
    owner.register_declarations((_activation_declaration(),))
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        for delta in prepared:
            owner.admit_observation_delta(delta)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)

    activation = context.closure_activation
    assert activation["admitted_delta_count"] == len(deltas)
    assert activation["ready_job_count"] == len(deltas)
    assert activation["first_owner_admission_latency_ns"] is not None
    assert activation["first_ready_job_latency_ns"] is not None
    assert activation["owner_admission_started_immediately"] is True
    handoff = context.closure_handoff_checkpoint_path
    assert handoff is not None and handoff.exists()
    payload = _read_json(handoff)
    assert payload is not None
    assert payload["admitted_batch_refs"] == [
        "batch:0",
        "batch:1",
        "batch:2",
        "batch:3",
    ]
    assert payload["current_owner_revision"] == owner.revision


def test_handoff_reconstructs_owner_without_repeating_solver_work(tmp_path) -> None:
    first_context = _activation_context(tmp_path, 1)
    first_context.closure_activation["contract_ref"] = CLOSURE_ACTIVATION_CONTRACT
    owner = BoundedStreamingSemanticOwner(document_ref="document:activation")
    owner.register_declarations((_activation_declaration(),))
    owner._activation_input_revision = 2
    calls = 0

    def solve(job: SolverJob) -> tuple[FactorProposal, ...]:
        nonlocal calls
        calls += 1
        return (_proposal(job),)

    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[first_context.document_ref] = first_context
    try:
        owner.admit_observation_delta(_activation_delta(0))
        job = owner._pending_jobs.popitem()[1]
        owner._in_flight_jobs[job.job_ref] = job
        receipt = PythonClosureExecutor({"declaration:activation": solve}).execute(job)
        owner.admit_solver_receipt(receipt)
        owner.reduce_dirty_groups()
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(first_context.document_ref, None)

    resumed_context = _activation_context(tmp_path, 1)
    replay = ClosureOwnerReplayContract(resumed_context)
    resumed_owner = BoundedStreamingSemanticOwner(document_ref="document:activation")
    resumed_owner.register_declarations((_activation_declaration(),))
    resumed_owner._activation_input_revision = 2
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[resumed_context.document_ref] = resumed_context
    try:
        replay.reconstruct(resumed_owner)
        # Re-presenting canonical input is an idempotent duplicate admission.
        resumed_owner.admit_observation_delta(_activation_delta(0))
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(resumed_context.document_ref, None)

    assert calls == 1
    assert resumed_owner.revision == owner.revision
    assert resumed_owner.materialized_reduction.graph_ref == (
        owner.materialized_reduction.graph_ref
    )
    assert resumed_owner.ledger.ledger_ref == owner.ledger.ledger_ref
    assert resumed_context.closure_activation["owner_reconstructed"] is True
    assert resumed_context.closure_activation["reconstructed_admission_count"] == 1
    assert resumed_context.closure_activation["reconstructed_receipt_count"] == 1
    assert resumed_context.closure_activation["duplicate_admission_count"] == 1


def test_handoff_rejects_incompatible_and_corrupt_checkpoints(tmp_path) -> None:
    context = _activation_context(tmp_path, 1)
    context.closure_activation["contract_ref"] = CLOSURE_ACTIVATION_CONTRACT
    owner = BoundedStreamingSemanticOwner(document_ref="document:activation")
    owner.register_declarations((_activation_declaration(),))
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        owner.admit_observation_delta(_activation_delta(0))
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)

    handoff = context.closure_handoff_checkpoint_path
    assert handoff is not None

    incompatible = _activation_context(tmp_path, 1)
    incompatible.build_key_sha256 = "different-build"
    incompatible_handoff = incompatible.closure_handoff_checkpoint_path
    assert incompatible_handoff is not None
    incompatible_handoff.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(handoff, incompatible_handoff)
    with pytest.raises(ValueError, match="identity mismatch"):
        ClosureOwnerReplayContract(incompatible)

    payload = _read_json(handoff)
    assert payload is not None
    payload["current_owner_revision"] = 999
    _atomic_write_json(handoff, payload)
    with pytest.raises(ValueError, match="identity mismatch"):
        ClosureOwnerReplayContract(_activation_context(tmp_path, 1))


def test_replay_artifacts_are_namespaced_by_replay_contract(tmp_path) -> None:
    context = _activation_context(tmp_path, 1)
    value = {"deltas": [{"delta_ref": "delta:1"}]}

    artifact_ref = _write_replay_artifact(
        context,
        artifact_kind="observation_delta_batch",
        value=value,
    )
    path = _replay_artifact_path(context, artifact_ref)
    assert path is not None and path.exists()
    payload = _read_json(path)
    assert payload is not None
    assert payload["owner_identity"] == {
        "document_ref": context.document_ref,
        "source_sha256": context.source_sha256,
        "parser_contract_ref": context.parser_contract_ref,
        "build_key_sha256": context.build_key_sha256,
        "handoff_schema_version": CLOSURE_HANDOFF_SCHEMA_VERSION,
        "handoff_contract_ref": CLOSURE_HANDOFF_CONTRACT,
        "artifact_schema_version": CLOSURE_REPLAY_ARTIFACT_SCHEMA_VERSION,
    }
    assert (
        _write_replay_artifact(
            context,
            artifact_kind="observation_delta_batch",
            value=value,
        )
        == artifact_ref
    )


def test_handoff_rejects_legacy_identity_without_rewriting_it(tmp_path) -> None:
    context = _activation_context(tmp_path, 1)
    context.closure_activation["contract_ref"] = CLOSURE_ACTIVATION_CONTRACT
    owner = BoundedStreamingSemanticOwner(document_ref=context.document_ref)
    owner.register_declarations((_activation_declaration(),))
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        owner.admit_observation_delta(_activation_delta(0))
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)

    handoff = context.closure_handoff_checkpoint_path
    assert handoff is not None
    legacy = _read_json(handoff)
    assert legacy is not None
    for key in (
        "handoff_schema_version",
        "handoff_contract_ref",
        "artifact_schema_version",
    ):
        legacy.pop(key)
    legacy.pop("checkpoint_ref")
    legacy["checkpoint_ref"] = "closure-handoff:" + canonical_sha256(
        {key: value for key, value in legacy.items() if key != "checkpoint_ref"}
    )
    _atomic_write_json(handoff, legacy)
    preserved = handoff.read_bytes()

    with pytest.raises(ValueError, match="identity mismatch"):
        ClosureOwnerReplayContract(_activation_context(tmp_path, 1))

    assert handoff.read_bytes() == preserved


def test_bounded_streaming_resume_reconstructs_exact_fixed_point(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")
    delta = _activation_delta(0)

    def run(context: SemanticExecutionContext):
        token = _CONTEXT.set(context)
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS[context.document_ref] = context
        try:
            return operational._streaming_semantic_build(
                document_ref=context.document_ref,
                source_ref="source:activation",
                observation_deltas=(delta,),
                base_factors=(),
                timings=StageTimingLedger(document_ref=context.document_ref),
                closure_workers=1,
                owner_partitions=1,
            )
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_CONTEXTS.pop(context.document_ref, None)
            _CONTEXT.reset(token)

    first_context = _activation_context(tmp_path, 1)
    first_build, first_metrics = run(first_context)
    second_context = _activation_context(tmp_path, 1)
    second_build, second_metrics = run(second_context)

    assert (
        first_build["fixed_point_certificate"]
        == second_build["fixed_point_certificate"]
    )
    assert (
        first_metrics["materialized_factor_refs"]
        == second_metrics["materialized_factor_refs"]
    )
    assert second_context.closure_activation["owner_reconstructed"] is True
    assert second_context.closure_activation["reused_leaf_count"] == 1
    assert second_context.closure_activation["computed_leaf_count"] == 0
    assert second_context.closure_counters["receipts_computed"] == 0
    assert second_context.closure_counters["reconstructed_receipts_admitted"] == 1


def test_activation_completion_stop_reuses_completed_worker_leaf(
    monkeypatch, tmp_path
) -> None:
    deltas = tuple(_activation_delta(index) for index in range(3))
    monkeypatch.setenv("SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION", "1")
    with pytest.raises(RuntimeError, match="activation completion"):
        prepare_closure_activation_leaves(
            context=_activation_context(tmp_path, 1), observation_deltas=deltas
        )
    monkeypatch.delenv("SENSIBLAW_CLOSURE_STOP_AFTER_ACTIVATION_COMPLETION")
    resumed = _activation_context(tmp_path, 1)
    prepared = prepare_closure_activation_leaves(
        context=resumed, observation_deltas=deltas
    )
    assert prepared == deltas
    assert resumed.closure_activation["reused_leaf_count"] >= 1


@pytest.mark.parametrize(
    ("environment_name", "expected_reconstructed_receipts"),
    (("SENSIBLAW_CLOSURE_STOP_AFTER_OWNER_BATCH_ADMISSIONS", 0),),
)
def test_owner_boundary_stops_resume_without_semantic_duplication(
    monkeypatch,
    tmp_path,
    environment_name,
    expected_reconstructed_receipts,
) -> None:
    delta = _activation_delta(0)

    def run(context: SemanticExecutionContext):
        token = _CONTEXT.set(context)
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS[context.document_ref] = context
        try:
            return operational._streaming_semantic_build(
                document_ref=context.document_ref,
                source_ref="source:activation",
                observation_deltas=(delta,),
                base_factors=(),
                timings=StageTimingLedger(document_ref=context.document_ref),
                closure_workers=1,
                owner_partitions=1,
            )
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_CONTEXTS.pop(context.document_ref, None)
            _CONTEXT.reset(token)

    monkeypatch.setenv(environment_name, "1")
    with pytest.raises(RuntimeError, match="checkpointed"):
        run(_activation_context(tmp_path, 1))
    monkeypatch.delenv(environment_name)

    resumed = _activation_context(tmp_path, 1)
    build, _metrics = run(resumed)
    assert build["fixed_point_certificate"]["local_fixed_point"] == "reached"
    assert resumed.closure_activation["owner_reconstructed"] is True
    assert resumed.closure_activation["reused_leaf_count"] == 1
    assert resumed.closure_activation["duplicate_admission_count"] == 1
    assert (
        resumed.closure_activation["reconstructed_receipt_count"]
        == expected_reconstructed_receipts
    )


def test_dirty_reduction_stop_reconstructs_admitted_receipt(
    monkeypatch, tmp_path
) -> None:
    context = _activation_context(tmp_path, 1)
    context.closure_activation["contract_ref"] = CLOSURE_ACTIVATION_CONTRACT
    owner = BoundedStreamingSemanticOwner(document_ref=context.document_ref)
    owner.register_declarations((_activation_declaration(),))
    owner._activation_input_revision = 2
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        owner.admit_observation_delta(_activation_delta(0))
        job = owner._pending_jobs.popitem()[1]
        owner._in_flight_jobs[job.job_ref] = job
        receipt = PythonClosureExecutor(
            {"declaration:activation": lambda value: (_proposal(value),)}
        ).execute(job)
        owner.admit_solver_receipt(receipt)
        monkeypatch.setenv("SENSIBLAW_CLOSURE_STOP_AFTER_DIRTY_REDUCTIONS", "1")
        with pytest.raises(RuntimeError, match="checkpointed dirty reductions"):
            owner.reduce_dirty_groups()
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)
    monkeypatch.delenv("SENSIBLAW_CLOSURE_STOP_AFTER_DIRTY_REDUCTIONS")

    resumed_context = _activation_context(tmp_path, 1)
    resumed_owner = BoundedStreamingSemanticOwner(
        document_ref=resumed_context.document_ref
    )
    resumed_owner.register_declarations((_activation_declaration(),))
    resumed_owner._activation_input_revision = 2
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[resumed_context.document_ref] = resumed_context
    try:
        ClosureOwnerReplayContract(resumed_context).reconstruct(resumed_owner)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(resumed_context.document_ref, None)

    assert resumed_owner.revision == owner.revision
    assert resumed_owner.materialized_reduction.graph_ref == (
        owner.materialized_reduction.graph_ref
    )
    assert resumed_context.closure_activation["reconstructed_receipt_count"] == 1
    assert resumed_context.closure_activation["reconstructed_reduction_count"] == 1


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


@pytest.mark.skipif(
    "fork" not in multiprocessing.get_all_start_methods(),
    reason="four-process activation fixture requires fork on this platform",
)
def test_four_process_stream_bounds_25_leaf_frontier(monkeypatch, tmp_path) -> None:
    from src.policy.parallel_typing_tail import shutdown_semantic_process_pool

    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "4")
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_MP_CONTEXT", "fork")
    context = _activation_context(tmp_path, 1)
    deltas = tuple(_activation_delta(index) for index in range(32))
    token = _CONTEXT.set(context)
    with _ACTIVE_LOCK:
        _ACTIVE_CONTEXTS[context.document_ref] = context
    try:
        build, metrics = operational._streaming_semantic_build(
            document_ref=context.document_ref,
            source_ref="source:activation",
            observation_deltas=deltas,
            base_factors=(),
            timings=StageTimingLedger(document_ref=context.document_ref),
            closure_workers=4,
            owner_partitions=4,
        )
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_CONTEXTS.pop(context.document_ref, None)
        _CONTEXT.reset(token)
        shutdown_semantic_process_pool()

    activation = context.closure_activation
    closure = context.closure_counters
    assert activation["leaf_count"] == 32
    assert activation["activation_owner_overlap_observed"] is True
    assert activation["max_buffered_leaves"] <= 8
    assert activation["max_buffered_bytes"] > 0
    assert activation["head_of_line_wait_ns"] >= 0
    assert len(activation["computed_worker_pids"]) >= 2
    assert metrics["kernel_telemetry"]["ready_jobs"]["max_batch_size"] <= 32
    assert closure["settled_groups_rescanned"] <= closure["dirty_groups_reduced"]
    assert build["fixed_point_certificate"]["local_fixed_point"] == "reached"
