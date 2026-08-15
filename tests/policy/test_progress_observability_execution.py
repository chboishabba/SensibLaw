from __future__ import annotations

from pathlib import Path
import pickle

from src.policy import parallel_typing_tail as tail
from src.policy.parallel_semantic_execution import SemanticExecutionContext
from src.policy.progress_observability_execution import (
    PROGRESS_ENVELOPE_SCHEMA_VERSION,
)


def _context(tmp_path: Path) -> SemanticExecutionContext:
    return SemanticExecutionContext(
        document_ref="document:progress-test",
        source_sha256="a" * 64,
        parser_contract_ref="parser:test:v1",
        build_key_sha256="b" * 64,
        typing_workers=1,
        leaf_capacity=2,
        hierarchy_arity=2,
        checkpoint_root=tmp_path,
        resource_ledger=None,
        run_ref="run:progress-test",
    )


def _worker(payload: dict[str, int]) -> dict[str, object]:
    return {"pid": 1234, "value": [payload["value"] * 2]}


def test_universal_envelope_is_logged_and_persisted(
    tmp_path: Path, capsys: object
) -> None:
    context = _context(tmp_path)

    row = context.sample(
        "local_typing_diagnostics:test",
        phase="typing_parent_waiting",
        counts={
            "leaves_completed": 2,
            "leaves_total": 4,
            "queue_count": 2,
            "in_flight_count": 2,
        },
        details={
            "current_work_key": "typing-leaf:2",
            "last_completion_at": "2026-08-04T00:00:00+00:00",
            "active_workers": 2,
            "wait_reason": "worker_results",
            "wait_dependency": "local_type_carrier_build",
            "wait_elapsed_ns": 30_000_000_000,
            "checkpoint_bytes_written": 4096,
            "checkpoint_bytes_reused": 2048,
            "batch_size": 2,
        },
    )

    envelope = row["progress_envelope"]
    assert envelope["schema_version"] == PROGRESS_ENVELOPE_SCHEMA_VERSION
    assert envelope["completed"] == 2
    assert envelope["total"] == 4
    assert envelope["wait_reason"] == "worker_results"
    assert envelope["active_workers"] == 2
    assert envelope["checkpoint_bytes_written"] == 4096
    latest = pickle.loads((tmp_path / "progress" / "latest.pkl").read_bytes())
    assert latest == envelope
    framed = (tmp_path / "progress" / "events.bin").read_bytes()
    frame_size = int.from_bytes(framed[:8], "big")
    assert pickle.loads(framed[8 : 8 + frame_size]) == envelope
    assert len(framed) == 8 + frame_size
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "SENSIBLAW_PROGRESS" in captured.err
    assert "typing_parent_waiting" in captured.err


def test_parent_rolls_up_leaf_completion_and_checkpoint_reuse(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("SENSIBLAW_SEMANTIC_PROCESS_WORKERS", "1")  # type: ignore[attr-defined]
    context = _context(tmp_path)
    payloads = ({"value": 1}, {"value": 2}, {"value": 3})
    identities = ({"value": 1}, {"value": 2}, {"value": 3})

    first, first_receipt = tail._execute_leaves(
        operation="test_rollup",
        context=context,
        payloads=payloads,
        input_identities=identities,
        worker=_worker,
        merge=lambda values: tuple(item for value in values for item in value),
    )

    assert first == (2, 4, 6)
    phases = [row["phase"] for row in context.kernel_timeline]
    assert phases[0] == "typing_parent_started"
    assert phases.count("typing_leaf_completed") == 3
    assert "typing_parent_aggregation_started" in phases
    assert phases[-1] == "typing_parent_aggregation_completed"
    leaf_events = [
        row
        for row in context.kernel_timeline
        if row["phase"] == "typing_leaf_completed"
    ]
    assert [row["counts"]["leaves_completed"] for row in leaf_events] == [1, 2, 3]
    assert all(row["counts"]["leaves_total"] == 3 for row in leaf_events)
    assert first_receipt["checkpoint_bytes_written"] > 0

    resumed_context = _context(tmp_path)
    second, second_receipt = tail._execute_leaves(
        operation="test_rollup",
        context=resumed_context,
        payloads=payloads,
        input_identities=identities,
        worker=_worker,
        merge=lambda values: tuple(item for value in values for item in value),
    )

    assert second == first
    assert second_receipt["logical_typing_ref"] == first_receipt["logical_typing_ref"]
    assert second_receipt["reused_leaf_count"] == 3
    assert second_receipt["checkpoint_bytes_reused"] > 0
    started = resumed_context.kernel_timeline[0]
    assert started["counts"]["leaves_completed"] == 3
    assert started["counts"]["leaves_total"] == 3
    assert started["counts"]["leaves_reused"] == 3
