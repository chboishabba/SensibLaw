"""Database-leased worker for resumable finalisation phases.

A finaliser receives a PostgreSQL checkpoint cursor and immutable manifest
references, not the in-memory semantic owner. Lease epochs fence stale workers,
and every completed batch advances the durable cursor transactionally.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic_ns
from types import TracebackType
from typing import Any, Callable, Mapping, Protocol, Self

from src.storage.postgres.distributed_semantic_execution_store import (
    DistributedSemanticExecutionStore,
    FinalizationLease,
    StaleSemanticLeaseError,
)


DISTRIBUTED_FINALIZATION_WORKER_CONTRACT = (
    "postgres-fenced-finalization-worker:v1"
)


class CursorLike(Protocol):
    rowcount: int

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def execute(self, query: str, parameters: Any = None) -> None: ...


class ConnectionLike(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def cursor(self) -> CursorLike: ...


ConnectionFactory = Callable[[], ConnectionLike]


@dataclass(frozen=True)
class FinalizationBatchResult:
    output_manifest_ref: str
    cursor_ordinal: int
    checkpoint_sha256: str
    metrics: Mapping[str, Any]


FinalizationExecutor = Callable[[FinalizationLease], FinalizationBatchResult]


@dataclass(frozen=True)
class FinalizationIterationReceipt:
    worker_ref: str
    leased_count: int
    completed_count: int
    stale_lease_count: int
    recovered_expired_count: int
    elapsed_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": DISTRIBUTED_FINALIZATION_WORKER_CONTRACT,
            "worker_ref": self.worker_ref,
            "leased_count": self.leased_count,
            "completed_count": self.completed_count,
            "stale_lease_count": self.stale_lease_count,
            "recovered_expired_count": self.recovered_expired_count,
            "elapsed_ns": self.elapsed_ns,
        }


class FinalizationLeaseHeartbeat:
    """Renew a finalisation lease without retaining the processing connection."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        lease: FinalizationLease,
        interval_seconds: float,
        lease_seconds: int,
    ) -> None:
        self.connection_factory = connection_factory
        self.lease = lease
        self.interval_seconds = interval_seconds
        self.lease_seconds = lease_seconds
        self.stop = Event()
        self.thread: Thread | None = None
        self.error: BaseException | None = None

    def __enter__(self) -> "FinalizationLeaseHeartbeat":
        self.thread = Thread(
            target=self._run,
            name=f"finalization-lease-{self.lease.checkpoint_ref}",
            daemon=True,
        )
        self.thread.start()
        return self

    def _run(self) -> None:
        while not self.stop.wait(self.interval_seconds):
            try:
                with self.connection_factory() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_finalization_checkpoint
                            SET lease_expires_at =
                                    CURRENT_TIMESTAMP
                                    + (%s * INTERVAL '1 second'),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE checkpoint_ref = %s
                              AND state_ref = 'leased'
                              AND lease_owner = %s
                              AND lease_epoch = %s
                            """,
                            (
                                self.lease_seconds,
                                self.lease.checkpoint_ref,
                                self.lease.lease_owner,
                                self.lease.lease_epoch,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise StaleSemanticLeaseError(
                                self.lease.checkpoint_ref
                            )
            except BaseException as error:
                self.error = error
                self.stop.set()
                return

    def assert_healthy(self) -> None:
        if self.error is not None:
            raise StaleSemanticLeaseError(
                self.lease.checkpoint_ref
            ) from self.error

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=max(1.0, self.interval_seconds * 2))
        if exc is None:
            self.assert_healthy()


class DistributedFinalizationWorker:
    """Continue one bounded finalisation phase from its PostgreSQL cursor."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory,
        executor: FinalizationExecutor,
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

    def _recover_and_lease(
        self, *, document_ref: str
    ) -> tuple[int, FinalizationLease | None]:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.semantic_finalization_checkpoint
                    SET state_ref = 'ready', lease_owner = NULL,
                        lease_expires_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE document_ref = %s
                      AND state_ref = 'leased'
                      AND lease_expires_at <= CURRENT_TIMESTAMP
                    """,
                    (document_ref,),
                )
                recovered = int(cursor.rowcount or 0)
                lease = self.store.lease_finalization_checkpoint(
                    cursor,
                    document_ref=document_ref,
                    worker_ref=self.worker_ref,
                    lease_seconds=self.lease_seconds,
                )
                return recovered, lease

    def _complete(
        self,
        lease: FinalizationLease,
        result: FinalizationBatchResult,
    ) -> None:
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self.store.complete_finalization_checkpoint(
                    cursor,
                    lease=lease,
                    output_manifest_ref=result.output_manifest_ref,
                    cursor_ordinal=result.cursor_ordinal,
                    checkpoint_sha256=result.checkpoint_sha256,
                    metrics={
                        "worker_contract_ref": (
                            DISTRIBUTED_FINALIZATION_WORKER_CONTRACT
                        ),
                        **dict(result.metrics),
                    },
                )

    def run_once(self, *, document_ref: str) -> FinalizationIterationReceipt:
        started = monotonic_ns()
        recovered, lease = self._recover_and_lease(document_ref=document_ref)
        if lease is None:
            return FinalizationIterationReceipt(
                worker_ref=self.worker_ref,
                leased_count=0,
                completed_count=0,
                stale_lease_count=0,
                recovered_expired_count=recovered,
                elapsed_ns=monotonic_ns() - started,
            )
        try:
            with FinalizationLeaseHeartbeat(
                connection_factory=self.connection_factory,
                lease=lease,
                interval_seconds=self.heartbeat_seconds,
                lease_seconds=self.lease_seconds,
            ) as heartbeat:
                result = self.executor(lease)
                heartbeat.assert_healthy()
            self._complete(lease, result)
        except StaleSemanticLeaseError:
            return FinalizationIterationReceipt(
                worker_ref=self.worker_ref,
                leased_count=1,
                completed_count=0,
                stale_lease_count=1,
                recovered_expired_count=recovered,
                elapsed_ns=monotonic_ns() - started,
            )
        return FinalizationIterationReceipt(
            worker_ref=self.worker_ref,
            leased_count=1,
            completed_count=1,
            stale_lease_count=0,
            recovered_expired_count=recovered,
            elapsed_ns=monotonic_ns() - started,
        )


__all__ = [
    "DISTRIBUTED_FINALIZATION_WORKER_CONTRACT",
    "DistributedFinalizationWorker",
    "FinalizationBatchResult",
    "FinalizationIterationReceipt",
    "FinalizationLeaseHeartbeat",
]
