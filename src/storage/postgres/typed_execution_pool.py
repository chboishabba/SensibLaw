"""Concurrent typed worker pool with append-only owner admission.

Workers compute immutable receipts concurrently.  Admission briefly locks the
owner revision row, allocates the next revision, and commits the typed result.
An owner revision advance does not invalidate work computed from the same
frontier, so revision contention never causes semantic recomputation.
"""

from __future__ import annotations

from dataclasses import replace
import multiprocessing as mp
import os
import pickle
from typing import Any, Callable

from src.policy.carriers.canonical import canonical_sha256
from src.storage.postgres import distributed_semantic_execution as execution


APPEND_ADMISSION_CONTRACT = "typed-owner-append-admission:v1"


def append_typed_delta(
    cursor: Any,
    *,
    lease: execution.Lease,
    delta: execution.TypedSemanticDelta,
) -> tuple[str, execution.TypedSemanticDelta]:
    """Fence the worker and append its immutable result to the owner stream."""

    cursor.execute(
        """
        SELECT state, lease_token, lease_epoch
        FROM execution.semantic_closure_job
        WHERE job_ref = %s
        FOR UPDATE
        """,
        (lease.manifest.job_ref,),
    )
    job_row = cursor.fetchone()
    if job_row is None:
        raise RuntimeError("leased typed closure job disappeared")
    state, lease_token, lease_epoch = (
        str(job_row[0]),
        job_row[1],
        int(job_row[2]),
    )
    if state == "completed":
        cursor.execute(
            """
            SELECT d.delta_ref, d.prior_revision, d.resulting_revision,
                   d.receipt_ref
            FROM execution.semantic_immutable_delta d
            WHERE d.run_ref = %s AND d.job_ref = %s
            """,
            (lease.manifest.run_ref, lease.manifest.job_ref),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise RuntimeError("completed job lacks its immutable typed delta")
        return "duplicate", delta
    if (
        state != "leased"
        or lease_token != lease.fence_token
        or lease_epoch != lease.lease_epoch
    ):
        return "stale", delta

    cursor.execute(
        """
        SELECT current_revision
        FROM execution.semantic_strict_owner_stream
        WHERE run_ref = %s AND owner_ref = %s
        FOR UPDATE
        """,
        (lease.manifest.run_ref, lease.manifest.owner_ref),
    )
    owner_row = cursor.fetchone()
    if owner_row is None:
        raise RuntimeError("typed owner stream is missing")
    prior_revision = int(owner_row[0])
    resulting_revision = prior_revision + 1
    admitted = replace(
        delta,
        prior_revision=prior_revision,
        resulting_revision=resulting_revision,
    )

    cursor.execute(
        """
        INSERT INTO execution.semantic_immutable_delta
            (delta_ref, run_ref, document_ref, owner_ref,
             resulting_revision, prior_revision, payload, payload_sha256,
             job_ref, lease_epoch, expected_owner_revision,
             receipt_ref, receipt_sha256)
        VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (delta_ref) DO NOTHING
        """,
        (
            admitted.delta_ref,
            lease.manifest.run_ref,
            lease.manifest.document_ref,
            lease.manifest.owner_ref,
            resulting_revision,
            prior_revision,
            bytes.fromhex(admitted.output_sha256),
            lease.manifest.job_ref,
            lease.lease_epoch,
            lease.expected_owner_revision,
            admitted.receipt.receipt_ref,
            bytes.fromhex(
                canonical_sha256(admitted.receipt.identity_payload())
            ),
        ),
    )
    if cursor.rowcount != 1:
        cursor.execute(
            """
            SELECT run_ref, owner_ref, prior_revision, resulting_revision
            FROM execution.semantic_immutable_delta
            WHERE delta_ref = %s
            """,
            (admitted.delta_ref,),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise RuntimeError("typed delta conflict has no existing row")
        if str(existing[0]) != lease.manifest.run_ref or str(existing[1]) != (
            lease.manifest.owner_ref
        ):
            raise RuntimeError("typed delta identity collided across owners")
        cursor.execute(
            """
            UPDATE execution.semantic_closure_job
            SET state = 'completed', lease_owner = NULL,
                lease_token = NULL, lease_expires_at = NULL
            WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
            """,
            (
                lease.manifest.job_ref,
                lease.fence_token,
                lease.lease_epoch,
            ),
        )
        return "duplicate", admitted

    execution._persist_solver_receipt(cursor, delta=admitted, lease=lease)
    cursor.execute(
        """
        INSERT INTO execution.semantic_strict_delta_admission
            (delta_ref, run_ref, owner_ref, resulting_revision,
             prior_revision, fence_token, lease_epoch)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            admitted.delta_ref,
            lease.manifest.run_ref,
            lease.manifest.owner_ref,
            resulting_revision,
            prior_revision,
            lease.fence_token,
            lease.lease_epoch,
        ),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_strict_owner_stream
        SET current_revision = %s
        WHERE run_ref = %s AND owner_ref = %s
          AND current_revision = %s
        """,
        (
            resulting_revision,
            lease.manifest.run_ref,
            lease.manifest.owner_ref,
            prior_revision,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("typed owner append lost its locked revision")
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET state = 'completed', lease_owner = NULL,
            lease_token = NULL, lease_expires_at = NULL
        WHERE job_ref = %s AND lease_token = %s AND lease_epoch = %s
        """,
        (
            lease.manifest.job_ref,
            lease.fence_token,
            lease.lease_epoch,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("typed job fence changed during append admission")
    return "accepted", admitted


def _worker_main(
    database_url: str,
    run_ref: str,
    worker_ref: str,
    execute: Callable[[execution.ImmutableJobManifest], Any],
    lease_seconds: int,
    result_queue: Any,
) -> None:
    import psycopg

    application_name = f"sensiblaw-typed:{run_ref}:{worker_ref}"
    connection = psycopg.connect(database_url, application_name=application_name)
    stats: dict[str, Any] = {
        "worker_ref": worker_ref,
        "worker_pid": os.getpid(),
        "backend_pid": None,
        "application_name": application_name,
        "leases": 0,
        "renewals": 0,
        "accepted": 0,
        "duplicates": 0,
        "stale": 0,
        "retries": 0,
        "failures": 0,
        "admission_contract": APPEND_ADMISSION_CONTRACT,
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            stats["backend_pid"] = int(cursor.fetchone()[0])
        connection.commit()
        while True:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = execution.lease_next_job(
                        cursor,
                        run_ref=run_ref,
                        worker_ref=worker_ref,
                        lease_seconds=lease_seconds,
                    )
            if lease is None:
                break
            stats["leases"] += 1
            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        if execution.renew_lease(
                            cursor,
                            lease=lease,
                            lease_seconds=lease_seconds,
                        ):
                            stats["renewals"] += 1
                delta = execution._coerce_delta(execute(lease.manifest), lease.manifest)
                with connection.transaction():
                    with connection.cursor() as cursor:
                        status, admitted = append_typed_delta(
                            cursor,
                            lease=lease,
                            delta=delta,
                        )
                        stats["duplicates" if status == "duplicate" else status] += 1
                        cursor.execute(
                            """
                            UPDATE execution.semantic_strict_job_attempt
                            SET state = %s, output_sha256 = %s,
                                completed_at = CURRENT_TIMESTAMP
                            WHERE attempt_ref = %s AND lease_epoch = %s
                            """,
                            (
                                "stale" if status == "stale" else "completed",
                                bytes.fromhex(admitted.output_sha256),
                                lease.attempt_ref,
                                lease.lease_epoch,
                            ),
                        )
            except Exception:
                stats["failures"] += 1
                stats["retries"] += 1
                with connection.transaction():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_strict_job_attempt
                            SET state = 'failed', completed_at = CURRENT_TIMESTAMP
                            WHERE attempt_ref = %s
                            """,
                            (lease.attempt_ref,),
                        )
                        cursor.execute(
                            """
                            UPDATE execution.semantic_closure_job
                            SET state = 'open', lease_owner = NULL,
                                lease_token = NULL, lease_expires_at = NULL,
                                retry_count = retry_count + 1
                            WHERE job_ref = %s AND lease_token = %s
                              AND lease_epoch = %s
                            """,
                            (
                                lease.manifest.job_ref,
                                lease.fence_token,
                                lease.lease_epoch,
                            ),
                        )
                raise
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO execution.semantic_worker_receipt
                        (receipt_ref, run_ref, document_ref, worker_ref,
                         worker_pid, backend_pid, application_name,
                         leases, renewals, accepted, duplicates, stale,
                         retries, failures, payload)
                    VALUES (%s, %s,
                            (SELECT document_ref FROM execution.semantic_run WHERE run_ref = %s),
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                    ON CONFLICT (run_ref, worker_ref) DO UPDATE SET
                        leases = EXCLUDED.leases,
                        renewals = EXCLUDED.renewals,
                        accepted = EXCLUDED.accepted,
                        duplicates = EXCLUDED.duplicates,
                        stale = EXCLUDED.stale,
                        retries = EXCLUDED.retries,
                        failures = EXCLUDED.failures,
                        payload = NULL
                    """,
                    (
                        f"worker-receipt:{run_ref}:{worker_ref}",
                        run_ref,
                        run_ref,
                        worker_ref,
                        stats["worker_pid"],
                        stats["backend_pid"],
                        application_name,
                        stats["leases"],
                        stats["renewals"],
                        stats["accepted"],
                        stats["duplicates"],
                        stats["stale"],
                        stats["retries"],
                        stats["failures"],
                    ),
                )
        result_queue.put(stats)
    except Exception as error:
        stats["error"] = repr(error)
        result_queue.put(stats)
        raise
    finally:
        connection.close()


class TypedProcessPostgresWorkerPool:
    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        worker_count: int,
        execute: Callable[[execution.ImmutableJobManifest], Any],
        lease_seconds: int = 60,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        try:
            pickle.dumps(execute)
        except (pickle.PicklingError, AttributeError, TypeError) as error:
            raise TypeError(
                "typed PostgreSQL worker executor must be spawn-picklable"
            ) from error
        self.database_url = database_url
        self.run_ref = run_ref
        self.worker_count = worker_count
        self.execute = execute
        self.lease_seconds = lease_seconds

    def run_until_idle(self) -> dict[str, Any]:
        context = mp.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(
                target=_worker_main,
                args=(
                    self.database_url,
                    self.run_ref,
                    f"{self.run_ref}:worker:{index}",
                    self.execute,
                    self.lease_seconds,
                    queue,
                ),
                name=f"sensiblaw-typed-worker-{index}",
            )
            for index in range(self.worker_count)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join()
        receipts: list[dict[str, Any]] = []
        while True:
            try:
                receipts.append(queue.get_nowait())
            except Exception:
                break
        if any(process.exitcode not in (0, None) for process in processes):
            errors = [row.get("error") for row in receipts if row.get("error")]
            detail = "; ".join(str(error) for error in errors) or (
                "child exited without acknowledgement"
            )
            raise RuntimeError(
                "typed PostgreSQL worker failed; durable leases remain recoverable: "
                + detail
            )
        return {
            "worker_pids": [
                int(row["worker_pid"]) for row in receipts if row.get("worker_pid")
            ],
            "backend_pids": [
                int(row["backend_pid"]) for row in receipts if row.get("backend_pid")
            ],
            "receipts": receipts,
        }


def install_typed_execution_pool() -> bool:
    if getattr(execution, "_typed_append_pool_installed", False):
        return False
    execution.ProcessPostgresWorkerPool = TypedProcessPostgresWorkerPool
    execution._typed_append_pool_installed = True
    return True


__all__ = [
    "APPEND_ADMISSION_CONTRACT",
    "TypedProcessPostgresWorkerPool",
    "append_typed_delta",
    "install_typed_execution_pool",
]
