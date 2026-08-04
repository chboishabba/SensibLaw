from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.storage.postgres.distributed_semantic_execution_store import (
    DistributedSemanticExecutionStore,
    SemanticJobLease,
    StaleSemanticLeaseError,
)


@dataclass
class FakeCursor:
    fetchall_rows: list[tuple[Any, ...]] = field(default_factory=list)
    fetchone_rows: list[tuple[Any, ...] | None] = field(default_factory=list)
    rowcount: int = 1
    executions: list[tuple[str, Any]] = field(default_factory=list)
    batch_sizes: list[int] = field(default_factory=list)

    def execute(self, query: str, parameters: Any = None) -> None:
        self.executions.append((query, parameters))

    def executemany(self, query: str, parameters: Any) -> None:
        rows = list(parameters)
        self.executions.append((query, rows))
        self.batch_sizes.append(len(rows))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self.fetchall_rows)

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.fetchone_rows.pop(0) if self.fetchone_rows else None


def test_lease_uses_skip_locked_and_returns_fencing_epoch() -> None:
    cursor = FakeCursor(
        fetchall_rows=[
            (
                "job:1",
                "document:1",
                "owner:1",
                "operation:v1",
                "manifest:1",
                3,
                4,
                10,
                "worker:a",
                7,
                {"input": "bounded"},
            )
        ]
    )
    store = DistributedSemanticExecutionStore()

    leases = store.lease_jobs(
        cursor,
        document_ref="document:1",
        worker_ref="worker:a",
        limit=4,
    )

    assert "FOR UPDATE SKIP LOCKED" in cursor.executions[0][0]
    assert leases[0].lease_epoch == 7
    assert leases[0].expected_owner_revision == 3


def test_renew_rejects_superseded_epoch() -> None:
    cursor = FakeCursor(rowcount=0)
    store = DistributedSemanticExecutionStore()

    with pytest.raises(StaleSemanticLeaseError):
        store.renew_lease(
            cursor,
            job_ref="job:1",
            worker_ref="worker:old",
            lease_epoch=1,
        )


def test_factor_persistence_never_builds_full_parameter_list() -> None:
    cursor = FakeCursor()
    store = DistributedSemanticExecutionStore()

    completed = store.persist_factor_revisions(
        cursor,
        manifest_ref="manifest:1",
        rows=(
            {
                "factor_ref": f"factor:{index}",
                "factor_revision_ref": f"revision:{index}",
            }
            for index in range(7)
        ),
        batch_size=3,
    )

    assert completed == 7
    assert cursor.batch_sizes == [3, 3, 1]


def test_admission_requires_current_lease_owner_and_epoch() -> None:
    cursor = FakeCursor(fetchone_rows=[("leased", "worker:new", 2, 0)])
    store = DistributedSemanticExecutionStore()
    stale = SemanticJobLease(
        job_ref="job:1",
        document_ref="document:1",
        owner_ref="owner:1",
        operation_contract_ref="operation:v1",
        input_manifest_ref="manifest:1",
        expected_owner_revision=0,
        canonical_ordinal=0,
        priority=1,
        lease_owner="worker:old",
        lease_epoch=1,
        payload={},
    )

    with pytest.raises(StaleSemanticLeaseError):
        store.admit_delta(
            cursor,
            lease=stale,
            delta_ref="delta:1",
            output_manifest_ref="output:1",
            output_manifest_sha256="00" * 32,
            payload={},
        )
