from __future__ import annotations

from src.pnf.streaming_fixed_point import (
    ObservationDelta,
    OwnerKey,
    PythonClosureExecutor,
    SolverJob,
)
from src.pnf.streaming_operator_executor import (
    STREAMING_OPERATOR_DECLARATION_REF,
    solve_operator_job,
)
from src.policy.activation_hot_path_execution import _descriptor_value
from src.policy.parallel_typing_tail import prepare_closure_activation_leaf_worker
from src.runtime.direct_closure_worker import execute_operator_solver_receipt


def _delta() -> ObservationDelta:
    return ObservationDelta(
        document_ref="document:direct-process",
        batch_ref="batch:0",
        scope_ref="sentence:0",
        sequence_no=0,
        parser_contract="parser:test",
        observation_refs=("observation:0",),
        observations=(
            {
                "observation_ref": "observation:0",
                "observation_type": "parser.token",
                "token": {
                    "index": 0,
                    "text": "must",
                    "lemma": "must",
                    "pos": "AUX",
                    "tag": "MD",
                    "dep": "ROOT",
                    "head_index": 0,
                    "start": 0,
                    "end": 4,
                },
            },
        ),
        token_start=0,
        token_end=1,
        char_start=0,
        char_end=4,
        token_count=1,
        coverage_barrier="sentence",
        coverage_complete=True,
    )


def _job() -> SolverJob:
    delta = _delta()
    return SolverJob(
        owner_key=OwnerKey(
            document_ref=delta.document_ref,
            scope_ref=delta.scope_ref,
            affected_index="semantic.operator_composition",
        ),
        declaration_ref=STREAMING_OPERATOR_DECLARATION_REF,
        input_revision=1,
        input_refs=delta.observation_refs,
        input_payload={
            "input_delta_ref": delta.delta_ref,
            "observation_delta": {
                "delta_ref": delta.delta_ref,
                "scope_ref": delta.scope_ref,
                "observations": delta.observations,
            },
        },
        rule_set_revision="v0_2",
        coverage_requirements=("sentence",),
        priority=40,
    )


def test_direct_process_worker_returns_canonical_solver_receipt() -> None:
    job = _job()
    canonical = PythonClosureExecutor(
        {STREAMING_OPERATOR_DECLARATION_REF: solve_operator_job}
    ).execute(job)
    direct = execute_operator_solver_receipt(job)

    assert direct.to_dict() == canonical.to_dict()
    assert direct.receipt_ref == canonical.receipt_ref


def test_coordinator_activation_descriptor_matches_old_worker_value() -> None:
    chunk = (_delta(),)
    previous = prepare_closure_activation_leaf_worker({"deltas": chunk})["value"]

    assert _descriptor_value(chunk) == previous


def test_bounded_execution_installs_direct_process_executor() -> None:
    from src.policy import bounded_operational_execution as bounded
    from src.policy.direct_process_closure_execution import DirectProcessClosurePool

    assert bounded.ThreadPoolExecutor is DirectProcessClosurePool
