from __future__ import annotations

from typing import Any

import pytest

from src.runtime.strict_postgres_execution import PostgresExecutionContext
from src.storage.postgres.distributed_semantic_execution import (
    DistributedFinalizationWorker,
    _digest,
)


class CheckpointCursor:
    def __init__(self, existing_digest: str | None = None) -> None:
        self.existing_digest = existing_digest
        self.executions: list[tuple[str, Any]] = []

    def execute(self, query: str, parameters: Any = None) -> None:
        self.executions.append((query, parameters))

    def fetchone(self) -> tuple[str] | None:
        if (
            "semantic_finalization_cursor" in self.executions[-1][0]
            and "SELECT" in self.executions[-1][0]
        ):
            return (self.existing_digest,) if self.existing_digest is not None else None
        return None


def _manifest() -> dict[str, Any]:
    return {"document_ref": "document:strict", "rows": [{"ref": "row:1"}]}


def test_checkpoint_uses_strict_cursor_contract_and_commits_batch_zero() -> None:
    cursor = CheckpointCursor()
    worker = DistributedFinalizationWorker(
        connection_factory=lambda: None, worker_ref="worker:strict"
    )

    cursor_ref = worker.checkpoint(
        cursor,
        run_ref="run:strict",
        document_ref="document:strict",
        owner_ref="owner:strict",
        cursor_revision=4,
        manifest=_manifest(),
    )

    assert cursor_ref == "finalization:run:strict:owner:strict:4"
    select_sql, _ = cursor.executions[0]
    insert_sql, parameters = cursor.executions[1]
    assert "semantic_finalization_cursor" in select_sql
    assert "semantic_finalization_checkpoint" not in select_sql
    assert "semantic_finalization_cursor" in insert_sql
    assert "batch_ordinal" in insert_sql
    assert "'committed'" in insert_sql
    assert parameters[0:5] == (
        cursor_ref,
        "run:strict",
        "document:strict",
        "owner:strict",
        4,
    )
    assert '"document_ref":"document:strict"' in parameters[5]
    assert len(parameters) == 7


def test_checkpoint_is_idempotent_for_identical_manifest() -> None:
    manifest = _manifest()
    worker = DistributedFinalizationWorker(
        connection_factory=lambda: None, worker_ref="worker:strict"
    )
    cursor = CheckpointCursor(existing_digest=_digest(manifest).hex())

    first = worker.checkpoint(
        cursor,
        run_ref="run:strict",
        document_ref="document:strict",
        owner_ref="owner:strict",
        cursor_revision=4,
        manifest=manifest,
    )
    second = worker.checkpoint(
        cursor,
        run_ref="run:strict",
        document_ref="document:strict",
        owner_ref="owner:strict",
        cursor_revision=4,
        manifest=manifest,
    )

    assert first == second


def test_checkpoint_rejects_mismatched_duplicate_digest() -> None:
    worker = DistributedFinalizationWorker(
        connection_factory=lambda: None, worker_ref="worker:strict"
    )
    cursor = CheckpointCursor(existing_digest="00" * 32)

    with pytest.raises(ValueError, match="checkpoint digest mismatch"):
        worker.checkpoint(
            cursor,
            run_ref="run:strict",
            document_ref="document:strict",
            owner_ref="owner:strict",
            cursor_revision=4,
            manifest=_manifest(),
        )


class ContextCursor:
    def __init__(self) -> None:
        self.executions: list[str] = []

    def execute(self, query: str, parameters: Any = None) -> None:
        self.executions.append(query)

    def fetchone(self) -> tuple[Any, ...]:
        if len(self.executions) == 1:
            return (
                "postgresql",
                4,
                "closure.fixed-point-certified",
                "kernel",
                2,
                "build",
                "contract",
                1,
                {"state": "reached"},
            )
        if len(self.executions) == 2:
            return (1, 2, 3, 4, 4, 1, 0, 1, 2, 1)
        return (0,)


def test_context_counts_strict_cursor_rows() -> None:
    cursor = ContextCursor()

    context = PostgresExecutionContext.from_cursor(
        cursor,
        run_ref="run:strict",
        document_ref="document:strict",
    )

    assert context.row_counts["finalization_checkpoints"] == 1
    assert "semantic_finalization_cursor" in cursor.executions[1]
    assert "semantic_finalization_checkpoint" not in cursor.executions[1]
