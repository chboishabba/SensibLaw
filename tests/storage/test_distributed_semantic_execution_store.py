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


def _lease() -> SemanticJobLease:
    return SemanticJobLease(
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

    with pytest.raises(StaleSemanticLeaseError):
        store.admit_delta(
            cursor,
            lease=_lease(),
            delta_ref="delta:1",
            output_manifest_ref="output:1",
            output_manifest_sha256="00" * 32,
            payload={},
        )


def test_completed_job_acknowledgement_is_idempotent() -> None:
    cursor = FakeCursor(
        fetchone_rows=[
            ("completed", None, 1, 0),
            ("delta:1", "job:1", "owner:1", 1, 0, 1, "accepted"),
        ]
    )
    store = DistributedSemanticExecutionStore()

    admission = store.admit_delta(
        cursor,
        lease=_lease(),
        delta_ref="delta:1",
        output_manifest_ref="output:1",
        output_manifest_sha256="00" * 32,
        payload={},
    )

    assert admission.state == "duplicate"
    assert admission.resulting_owner_revision == 1
    assert not any(
        "UPDATE execution.semantic_owner_stream" in query
        for query, _parameters in cursor.executions
    )


def test_finalization_checkpoint_lease_is_fenced() -> None:
    cursor = FakeCursor(
        fetchone_rows=[
            (
                "checkpoint:1",
                "document:1",
                9,
                "serialize_closure_receipt",
                512,
                1024,
                "worker:finalizer",
                3,
                "manifest:input",
            )
        ]
    )
    store = DistributedSemanticExecutionStore()

    lease = store.lease_finalization_checkpoint(
        cursor,
        document_ref="document:1",
        worker_ref="worker:finalizer",
    )
    assert lease is not None
    assert lease.lease_epoch == 3
    assert lease.cursor_ordinal == 512
    assert "FOR UPDATE SKIP LOCKED" in cursor.executions[0][0]

    store.complete_finalization_checkpoint(
        cursor,
        lease=lease,
        output_manifest_ref="manifest:output",
        cursor_ordinal=1024,
        checkpoint_sha256="11" * 32,
    )
    assert "lease_epoch = %s" in cursor.executions[-1][0]


def test_fixed_point_counts_include_unadmitted_deltas() -> None:
    cursor = FakeCursor(fetchone_rows=[(0, 0), (0, 0, 0), (2,)])
    store = DistributedSemanticExecutionStore()

    counts = store.fixed_point_counts(cursor, document_ref="document:1")

    assert counts["unadmitted_deltas"] == 2
    assert store.document_fixed(
        FakeCursor(fetchone_rows=[(0, 0), (0, 0, 0), (0,)]),
        document_ref="document:1",
    ) is True


def test_publication_commits_only_expected_staged_digest() -> None:
    cursor = FakeCursor(rowcount=1)
    store = DistributedSemanticExecutionStore()

    store.stage_publication(
        cursor,
        publication_ref="publication:1",
        document_ref="document:1",
        graph_manifest_ref="manifest:graph",
        certificate_ref="certificate:1",
        publication_digest="22" * 32,
    )
    store.commit_publication(
        cursor,
        publication_ref="publication:1",
        expected_digest="22" * 32,
    )

    assert "state_ref = 'staged'" in cursor.executions[0][0]
    assert "state_ref = 'committed'" in cursor.executions[1][0]
    assert "publication_digest = %s" in cursor.executions[1][0]
