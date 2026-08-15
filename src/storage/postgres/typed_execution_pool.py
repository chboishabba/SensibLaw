"""Concurrent typed computation with deterministic PostgreSQL admission.

Workers compute and persist immutable typed results concurrently.  They never
allocate owner revisions.  After all currently runnable work is staged, the
coordinator admits computed deltas in canonical ``(priority, job_ref)`` order
under one short owner-row lock.  This provides all of:

- commit-before-worker-ack durability;
- no JSON or JSONB state;
- no revision-stale semantic recomputation;
- deterministic owner revision history;
- concurrent semantic computation with narrowly serialized admission.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import pickle
from typing import Any, Callable

from src.policy.carriers.canonical import canonical_fields_sha256, canonical_sha256
from src.storage.postgres import distributed_semantic_execution as execution


COMPUTED_DELTA_CONTRACT = "typed-computed-delta:v1"
DETERMINISTIC_ADMISSION_CONTRACT = "typed-canonical-admission:v1"


def _semantic_output_sha256(delta: execution.TypedSemanticDelta) -> str:
    """Stable output identity independent of owner revision allocation."""

    return canonical_fields_sha256(
        COMPUTED_DELTA_CONTRACT,
        delta.delta_ref,
        delta.receipt.receipt_ref,
        delta.receipt.identity_payload(),
    )


def stage_typed_delta(
    cursor: Any,
    *,
    lease: execution.Lease,
    delta: execution.TypedSemanticDelta,
) -> str:
    """Persist one computed result before the worker reports success."""

    cursor.execute(
        """
        SELECT state, lease_token, lease_epoch
        FROM execution.semantic_closure_job
        WHERE job_ref = %s
        FOR UPDATE
        """,
        (lease.manifest.job_ref,),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("leased typed closure job disappeared")
    state, lease_token, lease_epoch = str(row[0]), row[1], int(row[2])
    if state in {"computed", "completed"}:
        cursor.execute(
            """
            SELECT delta_ref
            FROM execution.semantic_immutable_delta
            WHERE run_ref = %s AND job_ref = %s
            """,
            (lease.manifest.run_ref, lease.manifest.job_ref),
        )
        existing = cursor.fetchone()
        if existing is None or str(existing[0]) != delta.delta_ref:
            raise RuntimeError("computed job has a different immutable result")
        return "duplicate"
    if (
        state != "leased"
        or lease_token != lease.fence_token
        or lease_epoch != lease.lease_epoch
    ):
        cursor.execute(
            """
            UPDATE execution.semantic_strict_job_attempt
            SET state = 'stale', completed_at = CURRENT_TIMESTAMP
            WHERE attempt_ref = %s AND state = 'leased'
            """,
            (lease.attempt_ref,),
        )
        return "stale"

    semantic_digest = bytes.fromhex(_semantic_output_sha256(delta))
    receipt_digest = bytes.fromhex(canonical_sha256(delta.receipt.identity_payload()))
    cursor.execute(
        """
        INSERT INTO execution.semantic_immutable_delta
            (delta_ref, run_ref, document_ref, owner_ref,
             resulting_revision, prior_revision, payload, payload_sha256,
             job_ref, lease_epoch, expected_owner_revision,
             receipt_ref, receipt_sha256, computed_at, admitted_at)
        VALUES (%s, %s, %s, %s, NULL, NULL, NULL, %s, %s, %s, %s,
                %s, %s, CURRENT_TIMESTAMP, NULL)
        ON CONFLICT (run_ref, job_ref) DO NOTHING
        """,
        (
            delta.delta_ref,
            lease.manifest.run_ref,
            lease.manifest.document_ref,
            lease.manifest.owner_ref,
            semantic_digest,
            lease.manifest.job_ref,
            lease.lease_epoch,
            lease.expected_owner_revision,
            delta.receipt.receipt_ref,
            receipt_digest,
        ),
    )
    if cursor.rowcount != 1:
        cursor.execute(
            """
            SELECT delta_ref, encode(payload_sha256, 'hex')
            FROM execution.semantic_immutable_delta
            WHERE run_ref = %s AND job_ref = %s
            """,
            (lease.manifest.run_ref, lease.manifest.job_ref),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise RuntimeError("typed result conflict has no durable row")
        if str(existing[0]) != delta.delta_ref or str(existing[1]) != (
            semantic_digest.hex()
        ):
            raise RuntimeError("typed result identity changed across retry")
        return "duplicate"

    # The immutable delta exists before the typed receipt because the receipt's
    # foreign key proves which durable result it describes. Both commit in this
    # worker transaction before acknowledgement.
    execution._persist_solver_receipt(cursor, delta=delta, lease=lease)
    cursor.execute(
        """
        UPDATE execution.semantic_closure_job
        SET state = 'computed', lease_expires_at = NULL
        WHERE job_ref = %s AND state = 'leased'
          AND lease_token = %s AND lease_epoch = %s
        """,
        (
            lease.manifest.job_ref,
            lease.fence_token,
            lease.lease_epoch,
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("typed job fence changed while staging result")
    cursor.execute(
        """
        UPDATE execution.semantic_strict_job_attempt
        SET state = 'computed', output_sha256 = %s,
            completed_at = CURRENT_TIMESTAMP
        WHERE attempt_ref = %s AND lease_epoch = %s AND state = 'leased'
        """,
        (semantic_digest, lease.attempt_ref, lease.lease_epoch),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("typed attempt disappeared while staging result")
    return "computed"


def admit_computed_deltas(
    cursor: Any,
    *,
    run_ref: str,
    owner_ref: str,
) -> int:
    """Assign deterministic contiguous revisions to all staged results."""

    cursor.execute(
        """
        SELECT current_revision
        FROM execution.semantic_strict_owner_stream
        WHERE run_ref = %s AND owner_ref = %s
        FOR UPDATE
        """,
        (run_ref, owner_ref),
    )
    owner_row = cursor.fetchone()
    if owner_row is None:
        raise RuntimeError("typed owner stream is missing")
    revision = int(owner_row[0])

    cursor.execute(
        """
        SELECT j.job_ref, j.lease_token, j.lease_epoch,
               d.delta_ref, d.receipt_ref
        FROM execution.semantic_closure_job j
        JOIN execution.semantic_immutable_delta d
          ON d.run_ref = j.run_ref AND d.job_ref = j.job_ref
        WHERE j.run_ref = %s AND j.owner_ref = %s
          AND j.state = 'computed'
          AND d.prior_revision IS NULL
          AND d.resulting_revision IS NULL
        ORDER BY j.priority, j.job_ref
        FOR UPDATE OF j, d
        """,
        (run_ref, owner_ref),
    )
    staged = tuple(cursor.fetchall())
    for job_ref, fence_token, lease_epoch, delta_ref, _receipt_ref in staged:
        prior_revision = revision
        revision += 1
        cursor.execute(
            """
            UPDATE execution.semantic_immutable_delta
            SET prior_revision = %s, resulting_revision = %s,
                admitted_at = CURRENT_TIMESTAMP
            WHERE delta_ref = %s
              AND prior_revision IS NULL
              AND resulting_revision IS NULL
            """,
            (prior_revision, revision, str(delta_ref)),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("computed delta changed during canonical admission")
        cursor.execute(
            """
            INSERT INTO execution.semantic_strict_delta_admission
                (delta_ref, run_ref, owner_ref, resulting_revision,
                 prior_revision, fence_token, lease_epoch)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(delta_ref),
                run_ref,
                owner_ref,
                revision,
                prior_revision,
                str(fence_token),
                int(lease_epoch),
            ),
        )
        cursor.execute(
            """
            UPDATE execution.semantic_closure_job
            SET state = 'completed', lease_owner = NULL,
                lease_token = NULL, lease_expires_at = NULL
            WHERE job_ref = %s AND state = 'computed'
              AND lease_epoch = %s
            """,
            (str(job_ref), int(lease_epoch)),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("computed job changed during canonical admission")
        cursor.execute(
            """
            UPDATE execution.semantic_strict_job_attempt
            SET state = 'completed'
            WHERE job_ref = %s AND lease_epoch = %s AND state = 'computed'
            """,
            (str(job_ref), int(lease_epoch)),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("computed attempt changed during canonical admission")

    if staged:
        cursor.execute(
            """
            UPDATE execution.semantic_strict_owner_stream
            SET current_revision = %s
            WHERE run_ref = %s AND owner_ref = %s
              AND current_revision = %s
            """,
            (revision, run_ref, owner_ref, int(owner_row[0])),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("owner revision changed during canonical admission")
    return len(staged)


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
        "computed": 0,
        "duplicates": 0,
        "stale": 0,
        "retries": 0,
        "failures": 0,
        "computation_contract": COMPUTED_DELTA_CONTRACT,
        "admission_contract": DETERMINISTIC_ADMISSION_CONTRACT,
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
                        status = stage_typed_delta(
                            cursor,
                            lease=lease,
                            delta=delta,
                        )
                        stats[status] = stats.get(status, 0) + 1
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
                              AND state IN ('leased', 'computed')
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
                              AND state = 'leased'
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
                            %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, NULL)
                    ON CONFLICT (run_ref, worker_ref) DO UPDATE SET
                        leases = EXCLUDED.leases,
                        renewals = EXCLUDED.renewals,
                        accepted = 0,
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
    if getattr(execution, "_typed_deterministic_pool_installed", False):
        return False
    execution.ProcessPostgresWorkerPool = TypedProcessPostgresWorkerPool
    execution._typed_deterministic_pool_installed = True
    return True


__all__ = [
    "COMPUTED_DELTA_CONTRACT",
    "DETERMINISTIC_ADMISSION_CONTRACT",
    "TypedProcessPostgresWorkerPool",
    "admit_computed_deltas",
    "install_typed_execution_pool",
    "stage_typed_delta",
]
