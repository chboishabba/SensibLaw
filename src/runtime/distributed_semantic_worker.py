"""Database-leased worker loop for multi-machine semantic execution.

The worker never mutates semantic state directly. It leases immutable work,
renews the lease while computing, and submits a deterministic delta through the
fenced PostgreSQL admission protocol. Separate connections keep lease
heartbeats independent from long-running computation and result admission.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic_ns
from typing import Any, Callable, Mapping, Protocol

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres.distributed_semantic_execution_store import (
    DistributedSemanticExecutionStore,
    SemanticJobLease,
    StaleOwnerRevisionError,
    StaleSemanticLeaseError,
)


DISTRIBUTED_WORKER_CONTRACT = "postgres-fenced-semantic-worker:v1"


class CursorLike(Protocol):
    def execute(self, query: str, parameters: Any = None) -> None: ...


class ConnectionLike(AbstractContextManager[Any], Protocol):
    def cursor(self) -> AbstractContextManager[CursorLike]: ...


ConnectionFactory = Callable[[], ConnectionLike]
JobExecutor = Callable[[SemanticJobLease], "SemanticJobResult"]


@dataclass(frozen=True)
class SemanticJobResult:
    output_manifest_ref: str
    output_manifest_sha256: str
    payload: Mapping[str, Any]
    resource_receipt: Mapping[str, Any]
    delta_ref: str | None = None

    def resolved_delta_ref(self, lease: SemanticJobLease) -> str:
        return self.delta_ref or "semantic-delta:" + canonical_sha256(
            {
                "job_ref": lease.job_ref,
                "operation_contract_ref": lease.operation_contract_ref,
                "input_manifest_ref": lease.input_manifest_ref,
                "output_manifest_ref": self.output_manifest_ref,
                "output_manifest_sha256": self.output_manifest_sha256,
            }
        )


@dataclass(frozen=True)
class WorkerIterationReceipt:
    worker_ref: str
    leased_count: int
    accepted_count: int
    duplicate_count: int
    stale_lease_count: int
    stale_revision_count: int
    failed_count: int
    elapsed_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": DISTRIBUTED_WORKER_CONTRACT,
            "worker_ref": self.worker_ref,
            "leased_count": self.leased_count,
            "accepted_count": self.accepted_count,
            "duplicate_count": self.duplicate_count,
            "stale_lease_count": self.stale_lease_count,
            "stale_revision_count": self.stale_revision_count,
            "failed_count": self.failed_count,
            "elapsed_ns": self.elapsed_ns,
        }


class LeaseHeartbeat:
    """Renew one lease on an independent connection until computation finishes."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        store: DistributedSemanticExecutionStore,
        lease: SemanticJobLease,
        interval_seconds: float,
        lease_seconds: int,
    ) -> None:
        if interval_seconds <= 0 or lease_seconds < 1:
            raise ValueError("heartbeat interval and lease duration must be positive")
        self.connection_factory = connection_factory
        self.store = store
        self.lease = lease
        self.interval_seconds = interval_seconds
        self.lease_seconds = lease_seconds
        self.stop = Event()
        self.thread: Thread | None = None
        self.error: BaseException | None = None

    def __enter__(self) -> "LeaseHeartbeat":
        self.thread = Thread(
            target=self._run,
            name=f"semantic-lease-{self.lease.job_ref}",
            daemon=True,
        )
        self.thread.start()
        return self

    def _run(self) -> None:
        while not self.stop.wait(self.interval_seconds):
            try:
                with self.connection_factory() as connection:
                    with connection.cursor() as cursor:
                        self.store.renew_lease(
                            cursor,
                            job_ref=self.lease.job_ref,
                            worker_ref=self.lease.lease_owner,
                            lease_epoch=self.lease.lease_epoch,
                            lease_seconds=self.lease_seconds,
                        )
            except BaseException as error:  # captured and re-raised by owner thread
                self.error = error
                self.stop.set()
                return

    def assert_healthy(self) -> None:
        if self.error is not None:
            raise StaleSemanticLeaseError(self.lease.job_ref) from self.error

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=max(1.0, self.interval_seconds * 2))
        if exc is None:
            self.assert_healthy()


class DistributedSemanticWorker:
    """Lease and execute bounded semantic jobs from any authorised machine."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        executor: JobExecutor,
        worker_ref: str,
        store: DistributedSemanticExecutionStore | None = None,
        lease_seconds: int = 300,
        heartbeat_seconds: float | None = None,
    ) -> None:
        if not worker_ref:
            raise ValueError("worker_ref is required")
        if lease_seconds < 3:
            raise ValueError("lease_seconds must be at least three")
        self.connection_factory = connection_factory
        self.executor = executor
        self.worker_ref = worker_ref
        self.store = store or DistributedSemanticExecutionStore()
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds or max(1.0, lease_seconds / 3)

    def _lease(self, *, document_ref: str, limit: int) -> tuple[SemanticJobLease, ...]:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self.store.recover_expired_leases(
                    cursor,
                    document_ref=document_ref,
                )
                self.store.awaken_ready_jobs(cursor, document_ref=document_ref)
                return self.store.lease_jobs(
                    cursor,
                    document_ref=document_ref,
                    worker_ref=self.worker_ref,
                    limit=limit,
                    lease_seconds=self.lease_seconds,
                )

    def _admit(self, lease: SemanticJobLease, result: SemanticJobResult) -> str:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                admission = self.store.admit_delta(
                    cursor,
                    lease=lease,
                    delta_ref=result.resolved_delta_ref(lease),
                    output_manifest_ref=result.output_manifest_ref,
                    output_manifest_sha256=result.output_manifest_sha256,
                    payload=result.payload,
                    resource_receipt={
                        "worker_contract_ref": DISTRIBUTED_WORKER_CONTRACT,
                        **dict(result.resource_receipt),
                    },
                )
                return admission.state

    def run_once(
        self,
        *,
        document_ref: str,
        lease_limit: int = 1,
    ) -> WorkerIterationReceipt:
        if lease_limit < 1:
            raise ValueError("lease_limit must be positive")
        started = monotonic_ns()
        leases = self._lease(document_ref=document_ref, limit=lease_limit)
        accepted = 0
        duplicate = 0
        stale_lease = 0
        stale_revision = 0
        failed = 0
        for lease in leases:
            try:
                with LeaseHeartbeat(
                    connection_factory=self.connection_factory,
                    store=self.store,
                    lease=lease,
                    interval_seconds=self.heartbeat_seconds,
                    lease_seconds=self.lease_seconds,
                ) as heartbeat:
                    result = self.executor(lease)
                    heartbeat.assert_healthy()
                state = self._admit(lease, result)
                accepted += int(state == "accepted")
                duplicate += int(state == "duplicate")
            except StaleSemanticLeaseError:
                stale_lease += 1
            except StaleOwnerRevisionError:
                stale_revision += 1
            except Exception:
                failed += 1
                raise
        return WorkerIterationReceipt(
            worker_ref=self.worker_ref,
            leased_count=len(leases),
            accepted_count=accepted,
            duplicate_count=duplicate,
            stale_lease_count=stale_lease,
            stale_revision_count=stale_revision,
            failed_count=failed,
            elapsed_ns=monotonic_ns() - started,
        )


__all__ = [
    "DISTRIBUTED_WORKER_CONTRACT",
    "DistributedSemanticWorker",
    "LeaseHeartbeat",
    "SemanticJobResult",
    "WorkerIterationReceipt",
]
