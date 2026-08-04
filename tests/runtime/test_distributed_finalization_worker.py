from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.runtime.distributed_finalization_worker import (
    DistributedFinalizationWorker,
    FinalizationBatchResult,
)
from src.storage.postgres.distributed_semantic_execution_store import (
    FinalizationLease,
)


class FakeCursor:
    def __init__(self, *, rowcount: int = 0) -> None:
        self.rowcount = rowcount
        self.executions: list[tuple[str, Any]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def execute(self, query: str, parameters: Any = None) -> None:
        self.executions.append((query, parameters))


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


@dataclass
class FakeStore:
    lease: FinalizationLease | None
    completed: tuple[FinalizationLease, dict[str, Any]] | None = None

    def lease_finalization_checkpoint(self, cursor: Any, **kwargs: Any):
        return self.lease

    def complete_finalization_checkpoint(
        self, cursor: Any, *, lease: FinalizationLease, **kwargs: Any
    ) -> None:
        self.completed = (lease, dict(kwargs))


def _lease() -> FinalizationLease:
    return FinalizationLease(
        checkpoint_ref="checkpoint:1",
        document_ref="document:1",
        owner_revision=7,
        phase_ref="materialize_factor_reductions",
        cursor_ordinal=512,
        total_rows=1024,
        lease_owner="worker:finalizer",
        lease_epoch=3,
        input_manifest_ref="manifest:input",
    )


def test_finalizer_recovers_expired_and_completes_fenced_cursor() -> None:
    cursors = [FakeCursor(rowcount=2), FakeCursor(rowcount=1)]

    def connection_factory() -> FakeConnection:
        return FakeConnection(cursors.pop(0))

    store = FakeStore(_lease())
    observed: list[FinalizationLease] = []

    def execute(lease: FinalizationLease) -> FinalizationBatchResult:
        observed.append(lease)
        return FinalizationBatchResult(
            output_manifest_ref="manifest:output",
            cursor_ordinal=1024,
            checkpoint_sha256="11" * 32,
            metrics={"rows": 512},
        )

    worker = DistributedFinalizationWorker(
        connection_factory=connection_factory,
        executor=execute,
        worker_ref="worker:finalizer",
        store=store,  # type: ignore[arg-type]
        lease_seconds=300,
        heartbeat_seconds=100,
    )

    receipt = worker.run_once(document_ref="document:1")

    assert observed == [store.lease]
    assert receipt.recovered_expired_count == 2
    assert receipt.leased_count == 1
    assert receipt.completed_count == 1
    assert store.completed is not None
    completed_lease, values = store.completed
    assert completed_lease.lease_epoch == 3
    assert values["cursor_ordinal"] == 1024
    assert values["metrics"]["worker_contract_ref"].endswith(":v1")
