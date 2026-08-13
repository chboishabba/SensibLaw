"""Install canonical admission after concurrent typed computation.

Both process-backed and in-process workers stage typed results durably. Before
returning to the strict replay loop, the installed worker surface admits every
staged result in canonical owner and ``(priority, job_ref)`` order. A restart
sees and admits the same rows without recomputing them.
"""

from __future__ import annotations

from typing import Any, Callable

from src.storage.postgres import distributed_semantic_execution as execution
from src.storage.postgres.typed_execution_pool import (
    TypedProcessPostgresWorkerPool,
    admit_computed_deltas,
    stage_typed_delta,
)


def _admit_all_computed(
    connection_factory: Callable[[], Any],
    *,
    run_ref: str,
) -> int:
    connection = connection_factory()
    admitted = 0
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT owner_ref
                    FROM execution.semantic_closure_job
                    WHERE run_ref = %s AND state = 'computed'
                    ORDER BY owner_ref
                    """,
                    (run_ref,),
                )
                owner_refs = tuple(str(row[0]) for row in cursor.fetchall())
                for owner_ref in owner_refs:
                    admitted += admit_computed_deltas(
                        cursor,
                        run_ref=run_ref,
                        owner_ref=owner_ref,
                    )
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_closure_job
                    WHERE run_ref = %s AND state = 'computed'
                    """,
                    (run_ref,),
                )
                remaining = int(cursor.fetchone()[0])
                if remaining:
                    raise RuntimeError(
                        f"deterministic admission left {remaining} computed jobs"
                    )
    finally:
        connection.close()
    return admitted


class DeterministicAdmissionWorkerPool(TypedProcessPostgresWorkerPool):
    def run_until_idle(self) -> dict[str, Any]:
        result = super().run_until_idle()

        def connection_factory() -> Any:
            import psycopg

            return psycopg.connect(
                self.database_url,
                application_name=f"sensiblaw-admission:{self.run_ref}",
            )

        admitted = _admit_all_computed(
            connection_factory,
            run_ref=self.run_ref,
        )
        result["canonical_admission_count"] = admitted
        result["receipts"].append(
            {
                "worker_ref": f"{self.run_ref}:canonical-admission",
                "accepted": admitted,
                "duplicates": 0,
                "stale": 0,
                "admission_only": True,
            }
        )
        return result


class DeterministicAdmissionWorker(execution.DistributedSemanticWorker):
    """Typed in-process worker using the same stage-then-admit contract."""

    def run_once(self) -> str:
        connection = self.connection_factory()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = execution.lease_next_job(
                        cursor,
                        run_ref=self.run_ref,
                        worker_ref=self.worker_ref,
                        lease_seconds=self.lease_seconds,
                    )
            if lease is None:
                return "idle"
            try:
                delta = execution._coerce_delta(
                    self.execute(lease.manifest),
                    lease.manifest,
                )
                with connection.transaction():
                    with connection.cursor() as cursor:
                        return stage_typed_delta(
                            cursor,
                            lease=lease,
                            delta=delta,
                        )
            except Exception:
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
                              AND lease_epoch = %s AND state = 'leased'
                            """,
                            (
                                lease.manifest.job_ref,
                                lease.fence_token,
                                lease.lease_epoch,
                            ),
                        )
                raise
        finally:
            connection.close()

    def run_until_idle(self) -> dict[str, int]:
        counts = {
            "computed": 0,
            "accepted": 0,
            "duplicate": 0,
            "stale": 0,
            "idle": 0,
        }
        while True:
            status = self.run_once()
            counts[status] = counts.get(status, 0) + 1
            if status == "idle":
                break
        admitted = _admit_all_computed(
            self.connection_factory,
            run_ref=self.run_ref,
        )
        counts["accepted"] = admitted
        return counts


def install_deterministic_admission_execution() -> bool:
    if getattr(execution, "_deterministic_admission_installed", False):
        return False
    execution.ProcessPostgresWorkerPool = DeterministicAdmissionWorkerPool
    execution.DistributedSemanticWorker = DeterministicAdmissionWorker
    execution._deterministic_admission_installed = True
    return True


__all__ = [
    "DeterministicAdmissionWorker",
    "DeterministicAdmissionWorkerPool",
    "install_deterministic_admission_execution",
]
