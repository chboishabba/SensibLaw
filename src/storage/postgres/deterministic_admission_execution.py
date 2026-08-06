"""Install canonical admission after concurrent typed computation.

The underlying process pool stages typed results durably.  This wrapper admits
all staged results before returning to the strict replay loop, sorted first by
owner and then by each owner's ``(priority, job_ref)`` order.  A restart sees
and admits the same staged rows without recomputing them.
"""

from __future__ import annotations

from typing import Any

from src.storage.postgres import distributed_semantic_execution as execution
from src.storage.postgres.typed_execution_pool import (
    TypedProcessPostgresWorkerPool,
    admit_computed_deltas,
)


class DeterministicAdmissionWorkerPool(TypedProcessPostgresWorkerPool):
    def _admit_all_computed(self) -> int:
        import psycopg

        connection = psycopg.connect(
            self.database_url,
            application_name=f"sensiblaw-admission:{self.run_ref}",
        )
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
                        (self.run_ref,),
                    )
                    owner_refs = tuple(str(row[0]) for row in cursor.fetchall())
                    for owner_ref in owner_refs:
                        admitted += admit_computed_deltas(
                            cursor,
                            run_ref=self.run_ref,
                            owner_ref=owner_ref,
                        )
                    cursor.execute(
                        """
                        SELECT count(*)
                        FROM execution.semantic_closure_job
                        WHERE run_ref = %s AND state = 'computed'
                        """,
                        (self.run_ref,),
                    )
                    remaining = int(cursor.fetchone()[0])
                    if remaining:
                        raise RuntimeError(
                            f"deterministic admission left {remaining} computed jobs"
                        )
        finally:
            connection.close()
        return admitted

    def run_until_idle(self) -> dict[str, Any]:
        result = super().run_until_idle()
        admitted = self._admit_all_computed()
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


def install_deterministic_admission_execution() -> bool:
    if getattr(execution, "_deterministic_admission_installed", False):
        return False
    execution.ProcessPostgresWorkerPool = DeterministicAdmissionWorkerPool
    execution._deterministic_admission_installed = True
    return True


__all__ = [
    "DeterministicAdmissionWorkerPool",
    "install_deterministic_admission_execution",
]
