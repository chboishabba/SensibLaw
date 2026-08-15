"""Strict PostgreSQL execution policy with typed relational authority.

The coordinator schedules references and state transitions only.  It never
loads, mutates, serializes, or re-hashes semantic manifests.  Stable job input
lives in typed child relations; revision, lease, and fencing data live in small
mutable control-plane columns.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, Iterable, Mapping, Protocol

AUTHORITY_BACKEND = "postgresql"
STRICT_EXECUTION_CONTRACT = "postgresql-typed-leased-exact-execution:v2"


def _canonical_fields_sha256(*values: Any) -> str:
    """Resolve canonical hashing after the policy package is initialized."""

    from src.policy.carriers.canonical import canonical_fields_sha256

    return canonical_fields_sha256(*values)


def _execution_module() -> Any:
    from src.storage.postgres import distributed_semantic_execution

    return distributed_semantic_execution


class StrictExecutionError(RuntimeError):
    """A strict run could not prove its PostgreSQL authority contract."""

    def __init__(
        self,
        reason: str,
        *,
        diagnostic_path: str | None = None,
        kernel_key: str | None = None,
    ) -> None:
        self.reason = reason
        self.diagnostic_path = diagnostic_path
        self.kernel_key = kernel_key
        suffix = f" ({diagnostic_path})" if diagnostic_path else ""
        super().__init__(reason + suffix)


# These imports must follow ``StrictExecutionError``.  Importing the PNF
# package installs policy strategies, one of which imports this module again.
from src.pnf.streaming_fixed_point import SolverReceipt  # noqa: E402
from src.runtime.coordinator_lease_guard import (  # noqa: E402
    CoordinatorLeaseGuard,
    CoordinatorLeaseLost,
)
from src.storage.postgres.distributed_semantic_execution import (  # noqa: E402
    ImmutableJobManifest,
)


class StrictWorkerPool(Protocol):
    def run_until_idle(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PostgresExecutionContext:
    run_ref: str
    document_ref: str
    authority_backend: str
    row_counts: Mapping[str, int]
    owner_revision: int
    lifecycle: str
    obligations: Mapping[str, int]
    kernel_key: str | None = None
    worker_budget: int | None = None
    build_key_sha256: str | None = None
    operation_contract_ref: str | None = None
    round_ordinal: int = 0
    fixed_point_state: str | None = None
    fixed_point_round_count: int | None = None
    fixed_point_zero_change_round: int | None = None
    fixed_point_owner_revision: int | None = None
    fixed_point_sha256: str | None = None

    @classmethod
    def from_cursor(
        cls,
        cursor: Any,
        *,
        run_ref: str,
        document_ref: str,
    ) -> "PostgresExecutionContext":
        cursor.execute(
            """
            SELECT authority_backend, owner_revision, lifecycle, kernel_key,
                   worker_budget, build_key_sha256, operation_contract_ref,
                   round_ordinal, fixed_point_state,
                   fixed_point_round_count, fixed_point_zero_change_round,
                   fixed_point_owner_revision,
                   encode(fixed_point_sha256, 'hex')
            FROM execution.semantic_run
            WHERE run_ref = %s AND document_ref = %s
            """,
            (run_ref, document_ref),
        )
        row = cursor.fetchone()
        if row is None:
            raise StrictExecutionError(
                "postgresql_authority_missing",
                kernel_key="strict.execution_context",
            )
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM execution.semantic_strict_owner_stream WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_closure_job WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_strict_job_attempt a JOIN execution.semantic_closure_job j USING (job_ref) WHERE j.run_ref = %s),
              (SELECT count(*) FROM execution.semantic_immutable_delta WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_strict_delta_admission WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_finalization_cursor WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_publication WHERE run_ref = %s AND state = 'committed'),
              (SELECT count(*) FROM execution.semantic_kernel_registration WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_lifecycle_event WHERE run_ref = %s),
              (SELECT count(*) FROM execution.semantic_owner_revision_history WHERE run_ref = %s)
            """,
            (run_ref,) * 10,
        )
        counts_row = cursor.fetchone() or (0,) * 10
        names = (
            "owner_stream",
            "jobs",
            "attempts",
            "immutable_deltas",
            "fenced_admissions",
            "finalization_checkpoints",
            "committed_publications",
            "kernel_registrations",
            "lifecycle_events",
            "revision_history",
        )
        counts = dict(
            zip(names, (int(value or 0) for value in counts_row), strict=True)
        )
        cursor.execute(
            """
            SELECT
                count(*) FILTER (WHERE state = 'open'),
                count(*) FILTER (WHERE state = 'leased'),
                count(*) FILTER (WHERE state = 'failed')
            FROM execution.semantic_closure_job
            WHERE run_ref = %s
            """,
            (run_ref,),
        )
        open_count, leased_count, failed_count = cursor.fetchone() or (0, 0, 0)
        return cls(
            run_ref=run_ref,
            document_ref=document_ref,
            authority_backend=str(row[0]),
            owner_revision=int(row[1]),
            lifecycle=str(row[2]),
            row_counts=counts,
            obligations={
                "open_jobs": int(open_count or 0),
                "leased_jobs": int(leased_count or 0),
                "failed_jobs": int(failed_count or 0),
            },
            kernel_key=str(row[3]) if row[3] else None,
            worker_budget=int(row[4]) if row[4] is not None else None,
            build_key_sha256=str(row[5]) if row[5] else None,
            operation_contract_ref=str(row[6]) if row[6] else None,
            round_ordinal=int(row[7] or 0),
            fixed_point_state=str(row[8]) if row[8] else None,
            fixed_point_round_count=int(row[9]) if row[9] is not None else None,
            fixed_point_zero_change_round=(
                int(row[10]) if row[10] is not None else None
            ),
            fixed_point_owner_revision=(int(row[11]) if row[11] is not None else None),
            fixed_point_sha256=str(row[12]) if row[12] else None,
        )


def assert_strict_context(context: PostgresExecutionContext) -> None:
    if context.authority_backend != AUTHORITY_BACKEND:
        raise StrictExecutionError(
            "postgresql_authority_missing",
            kernel_key="strict.execution_context",
        )
    if (
        context.row_counts["owner_stream"] < 1
        or context.row_counts["kernel_registrations"] < 1
    ):
        raise StrictExecutionError(
            "postgresql_authority_missing",
            kernel_key="strict.execution_context",
        )
    if (
        context.row_counts["immutable_deltas"]
        != context.row_counts["fenced_admissions"]
    ):
        raise StrictExecutionError(
            "strict_revision_admission_invalid",
            kernel_key="strict.admission",
        )
    if any(context.obligations.values()):
        raise StrictExecutionError(
            "strict_obligations_unresolved",
            kernel_key="strict.closure_gate",
        )
    if not context.kernel_key or not context.worker_budget or context.worker_budget < 1:
        raise StrictExecutionError(
            "unregistered_kernel",
            kernel_key=context.kernel_key or "strict.kernel",
        )
    if not context.build_key_sha256 or not context.operation_contract_ref:
        raise StrictExecutionError(
            "strict_authority_identity_missing",
            kernel_key="strict.execution_context",
        )
    if context.fixed_point_state != "reached":
        raise StrictExecutionError(
            "strict_fixed_point_incomplete",
            kernel_key="strict.closure_gate",
        )
    if context.fixed_point_owner_revision != context.owner_revision:
        raise StrictExecutionError(
            "strict_fixed_point_revision_mismatch",
            kernel_key="strict.closure_gate",
        )
    expected_digest = _canonical_fields_sha256(
        context.run_ref,
        context.document_ref,
        context.fixed_point_round_count,
        context.fixed_point_zero_change_round,
        context.fixed_point_owner_revision,
        "reached",
    )
    if context.fixed_point_sha256 != expected_digest:
        raise StrictExecutionError(
            "strict_fixed_point_digest_mismatch",
            kernel_key="strict.closure_gate",
        )


def connect_postgres(database_url: str) -> Any:
    if not database_url:
        raise StrictExecutionError(
            "postgresql_authority_missing",
            kernel_key="strict.connection",
        )
    try:
        import psycopg

        return psycopg.connect(database_url)
    except Exception as error:
        raise StrictExecutionError(
            "postgresql_authority_missing",
            diagnostic_path=str(error),
            kernel_key="strict.connection",
        ) from error


class PostgresLeasedExecution:
    """Coordinate process workers through typed PostgreSQL state only."""

    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        document_ref: str,
        worker_count: int,
        kernel_key: str = "streaming_closure",
        build_key_sha256: str = "unknown",
        operation_contract_ref: str = STRICT_EXECUTION_CONTRACT,
        max_rounds: int = 16384,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        self.database_url = database_url
        self.run_ref = run_ref
        self.document_ref = document_ref
        self.worker_count = worker_count
        self.kernel_key = kernel_key
        self.build_key_sha256 = build_key_sha256
        self.operation_contract_ref = operation_contract_ref
        self.max_rounds = int(os.environ.get("SENSIBLAW_MAX_ROUNDS", str(max_rounds)))
        self.coordinator_lease_seconds = int(
            os.environ.get("SENSIBLAW_COORDINATOR_LEASE_SECONDS", "90")
        )

    def connection_factory(self) -> Any:
        return connect_postgres(self.database_url)

    def begin(self, *, owner_ref: str) -> None:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    module = _execution_module()
                    module.create_run(
                        cursor,
                        run_ref=self.run_ref,
                        document_ref=self.document_ref,
                        kernel_key=self.kernel_key,
                        worker_budget=self.worker_count,
                    )
                    cursor.execute(
                        """
                        UPDATE execution.semantic_run
                        SET build_key_sha256 = %s,
                            operation_contract_ref = %s,
                            max_rounds = %s,
                            round_ordinal = 0,
                            sealed = FALSE,
                            fixed_point_certificate = NULL,
                            fixed_point_state = NULL,
                            fixed_point_round_count = NULL,
                            fixed_point_zero_change_round = NULL,
                            fixed_point_owner_revision = NULL,
                            fixed_point_sha256 = NULL
                        WHERE run_ref = %s
                        """,
                        (
                            self.build_key_sha256,
                            self.operation_contract_ref,
                            self.max_rounds,
                            self.run_ref,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO execution.semantic_strict_owner_stream
                            (run_ref, owner_ref)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (self.run_ref, owner_ref),
                    )
                    module.register_kernel(
                        cursor,
                        run_ref=self.run_ref,
                        kernel_key=self.kernel_key,
                        worker_budget=self.worker_count,
                    )
                    module.record_lifecycle(
                        cursor,
                        run_ref=self.run_ref,
                        lifecycle="closure.reducing",
                        detail={"owner_ref": owner_ref},
                    )
        finally:
            connection.close()

    def _coordinator_guard(self) -> CoordinatorLeaseGuard:
        return CoordinatorLeaseGuard(
            database_url=self.database_url,
            run_ref=self.run_ref,
            lease_seconds=self.coordinator_lease_seconds,
        )

    def run_frontier(
        self,
        manifests: Iterable[ImmutableJobManifest],
        *,
        execute: Callable[[ImmutableJobManifest], Any],
        apply: Callable[[SolverReceipt, int], None],
        owner_ref: str,
        starting_revision: int = 0,
        rehydrate: Callable[[ImmutableJobManifest], None] | None = None,
    ) -> dict[str, Any]:
        self.begin(owner_ref=owner_ref)
        try:
            with self._coordinator_guard() as coordinator:
                return self._run_frontier_under_lease(
                    manifests,
                    execute=execute,
                    apply=apply,
                    owner_ref=owner_ref,
                    starting_revision=starting_revision,
                    rehydrate=rehydrate,
                    coordinator=coordinator,
                )
        except CoordinatorLeaseLost as error:
            raise StrictExecutionError(
                "strict_coordinator_lease_lost",
                diagnostic_path=str(error),
                kernel_key="strict.coordinator",
            ) from error

    def _round_digest(
        self,
        *,
        round_ordinal: int,
        input_revision: int,
        output_revision: int,
        job_count: int,
        delta_count: int,
        awakened_count: int,
        state: str,
    ) -> bytes:
        return bytes.fromhex(
            _canonical_fields_sha256(
                self.run_ref,
                self.document_ref,
                round_ordinal,
                input_revision,
                output_revision,
                job_count,
                delta_count,
                awakened_count,
                state,
            )
        )

    def _record_round(
        self,
        cursor: Any,
        *,
        round_ordinal: int,
        input_revision: int,
        output_revision: int,
        job_count: int,
        delta_count: int,
        awakened_count: int,
        state: str,
    ) -> None:
        round_ref = f"round:{self.run_ref}:{round_ordinal}"
        cursor.execute(
            """
            INSERT INTO execution.semantic_round_manifest
                (round_ref, run_ref, document_ref, round_ordinal,
                 input_owner_revision, output_owner_revision, job_count,
                 delta_count, changed_owner_count, awakened_job_count,
                 manifest, manifest_sha256, state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NULL, %s, %s)
            ON CONFLICT (round_ref) DO UPDATE SET
                output_owner_revision = EXCLUDED.output_owner_revision,
                job_count = EXCLUDED.job_count,
                delta_count = EXCLUDED.delta_count,
                changed_owner_count = EXCLUDED.changed_owner_count,
                awakened_job_count = EXCLUDED.awakened_job_count,
                manifest = NULL,
                manifest_sha256 = EXCLUDED.manifest_sha256,
                state = EXCLUDED.state
            """,
            (
                round_ref,
                self.run_ref,
                self.document_ref,
                round_ordinal,
                input_revision,
                output_revision,
                job_count,
                delta_count,
                1 if output_revision != input_revision else 0,
                awakened_count,
                self._round_digest(
                    round_ordinal=round_ordinal,
                    input_revision=input_revision,
                    output_revision=output_revision,
                    job_count=job_count,
                    delta_count=delta_count,
                    awakened_count=awakened_count,
                    state=state,
                ),
                state,
            ),
        )

    def _run_frontier_under_lease(
        self,
        manifests: Iterable[ImmutableJobManifest],
        *,
        execute: Callable[[ImmutableJobManifest], Any],
        apply: Callable[[SolverReceipt, int], None],
        owner_ref: str,
        starting_revision: int,
        rehydrate: Callable[[ImmutableJobManifest], None] | None,
        coordinator: CoordinatorLeaseGuard,
    ) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    enqueued = _execution_module().enqueue_canonical_closure_jobs(
                        cursor,
                        manifests,
                    )
            receipts: dict[str, Any] = {
                "enqueued": enqueued,
                "accepted": 0,
                "duplicate": 0,
                "stale": 0,
                "workers": self.worker_count,
                "worker_pids": [],
                "backend_pids": [],
            }
            pool = _execution_module().ProcessPostgresWorkerPool(
                database_url=self.database_url,
                run_ref=self.run_ref,
                worker_count=self.worker_count,
                execute=execute,
            )
            current_revision = starting_revision
            for round_ordinal in range(1, self.max_rounds + 1):
                coordinator.assert_current()
                round_input_revision = current_revision
                worker_receipt = pool.run_until_idle()
                coordinator.assert_current()
                receipts["workers"] = len(worker_receipt["worker_pids"])
                receipts["worker_pids"].extend(worker_receipt["worker_pids"])
                receipts["backend_pids"].extend(worker_receipt["backend_pids"])
                for worker in worker_receipt["receipts"]:
                    receipts["accepted"] += int(worker.get("accepted", 0))
                    receipts["duplicate"] += int(worker.get("duplicates", 0))
                    receipts["stale"] += int(worker.get("stale", 0))

                with connection.transaction():
                    with connection.cursor() as cursor:
                        replayed = _execution_module().replay_accepted_deltas(
                            cursor,
                            run_ref=self.run_ref,
                            owner_ref=owner_ref,
                            apply=apply,
                            starting_revision=current_revision,
                            rehydrate=rehydrate,
                        )
                        current_revision += replayed
                        cursor.execute(
                            """
                            SELECT current_revision
                            FROM execution.semantic_strict_owner_stream
                            WHERE run_ref = %s AND owner_ref = %s
                            """,
                            (self.run_ref, owner_ref),
                        )
                        owner_row = cursor.fetchone()
                        if owner_row is None:
                            raise StrictExecutionError(
                                "postgresql_authority_missing",
                                kernel_key="strict.owner_stream",
                            )
                        authoritative_revision = int(owner_row[0])
                        if authoritative_revision != current_revision:
                            raise StrictExecutionError(
                                "strict_replay_revision_lag",
                                diagnostic_path=(
                                    f"database={authoritative_revision}, "
                                    f"coordinator={current_revision}"
                                ),
                                kernel_key="strict.replay",
                            )
                        cursor.execute(
                            """
                            UPDATE execution.semantic_run
                            SET owner_revision = %s, round_ordinal = %s
                            WHERE run_ref = %s
                            """,
                            (current_revision, round_ordinal, self.run_ref),
                        )
                        cursor.execute(
                            """
                            SELECT
                                count(*) FILTER (WHERE state = 'open'),
                                count(*) FILTER (WHERE state = 'leased'),
                                count(*) FILTER (WHERE state = 'failed')
                            FROM execution.semantic_closure_job
                            WHERE run_ref = %s
                            """,
                            (self.run_ref,),
                        )
                        open_jobs, leased_jobs, failed_jobs = (
                            int(value or 0) for value in cursor.fetchone()
                        )
                        if failed_jobs:
                            self._record_round(
                                cursor,
                                round_ordinal=round_ordinal,
                                input_revision=round_input_revision,
                                output_revision=current_revision,
                                job_count=open_jobs + leased_jobs + failed_jobs,
                                delta_count=replayed,
                                awakened_count=open_jobs,
                                state="failed",
                            )
                            raise StrictExecutionError(
                                "strict_worker_failure",
                                diagnostic_path=f"failed_jobs={failed_jobs}",
                                kernel_key="strict.closure_gate",
                            )
                        frontier_jobs = open_jobs + leased_jobs
                        fixed_point = frontier_jobs == 0 and replayed == 0
                        self._record_round(
                            cursor,
                            round_ordinal=round_ordinal,
                            input_revision=round_input_revision,
                            output_revision=current_revision,
                            job_count=frontier_jobs,
                            delta_count=replayed,
                            awakened_count=open_jobs,
                            state="fixed_point" if fixed_point else "committed",
                        )
                        if fixed_point:
                            digest_hex = _canonical_fields_sha256(
                                self.run_ref,
                                self.document_ref,
                                round_ordinal,
                                round_ordinal,
                                current_revision,
                                "reached",
                            )
                            cursor.execute(
                                """
                                UPDATE execution.semantic_run
                                SET fixed_point_certificate = NULL,
                                    fixed_point_state = 'reached',
                                    fixed_point_round_count = %s,
                                    fixed_point_zero_change_round = %s,
                                    fixed_point_owner_revision = %s,
                                    fixed_point_sha256 = %s,
                                    round_ordinal = %s
                                WHERE run_ref = %s
                                """,
                                (
                                    round_ordinal,
                                    round_ordinal,
                                    current_revision,
                                    bytes.fromhex(digest_hex),
                                    round_ordinal,
                                    self.run_ref,
                                ),
                            )
                            _execution_module().record_lifecycle(
                                cursor,
                                run_ref=self.run_ref,
                                lifecycle="closure.fixed-point-certified",
                                detail={
                                    "owner_ref": owner_ref,
                                    "owner_revision": current_revision,
                                    "round_count": round_ordinal,
                                },
                            )
                            coordinator.assert_current()
                            receipts["replayed"] = current_revision - starting_revision
                            receipts["round_count"] = round_ordinal
                            return receipts
            raise StrictExecutionError(
                "strict_fixed_point_incomplete: maximum rounds exhausted",
                kernel_key="strict.closure_gate",
            )
        finally:
            connection.close()

    def finalize(self, *, owner_ref: str, manifest: Mapping[str, Any]) -> str:
        try:
            with self._coordinator_guard() as coordinator:
                connection = self.connection_factory()
                try:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            context = PostgresExecutionContext.from_cursor(
                                cursor,
                                run_ref=self.run_ref,
                                document_ref=self.document_ref,
                            )
                            assert_strict_context(context)
                            coordinator.assert_current()
                            cursor.execute(
                                """
                                UPDATE execution.semantic_run
                                SET sealed = TRUE,
                                    lifecycle = 'finalization.sealed'
                                WHERE run_ref = %s
                                """,
                                (self.run_ref,),
                            )
                            worker = _execution_module().DistributedFinalizationWorker(
                                connection_factory=self.connection_factory,
                                worker_ref=f"{self.run_ref}:finalizer",
                            )
                            worker.checkpoint(
                                cursor,
                                run_ref=self.run_ref,
                                document_ref=self.document_ref,
                                owner_ref=owner_ref,
                                cursor_revision=context.owner_revision,
                                manifest=manifest,
                            )
                    coordinator.assert_current()
                    return _execution_module().publish_in_fresh_process(
                        database_url=self.database_url,
                        run_ref=self.run_ref,
                        document_ref=self.document_ref,
                        manifest=manifest,
                    )
                finally:
                    connection.close()
        except CoordinatorLeaseLost as error:
            raise StrictExecutionError(
                "strict_coordinator_lease_lost",
                diagnostic_path=str(error),
                kernel_key="strict.coordinator",
            ) from error


def strict_execution_metadata() -> dict[str, str]:
    return {
        "execution_strategy": STRICT_EXECUTION_CONTRACT,
        "authority_backend": AUTHORITY_BACKEND,
        "local_replay": "forbidden",
        "kernel_contract": STRICT_EXECUTION_CONTRACT,
        "worker_backend": "spawned-postgresql-processes",
        "lease_ttl_seconds": "60",
        "coordinator_lease_seconds": os.environ.get(
            "SENSIBLAW_COORDINATOR_LEASE_SECONDS",
            "90",
        ),
        "max_rounds": os.environ.get("SENSIBLAW_MAX_ROUNDS", "16384"),
        "retention": "retained-by-default",
        "serialization": "forbidden",
    }


__all__ = [
    "StrictExecutionError",
    "StrictWorkerPool",
    "PostgresExecutionContext",
    "PostgresLeasedExecution",
    "assert_strict_context",
    "connect_postgres",
    "strict_execution_metadata",
]
