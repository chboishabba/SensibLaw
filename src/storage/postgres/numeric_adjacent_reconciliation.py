"""Fenced execution of overlapping adjacent-region PNF fibres."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.pnf.numeric_hyperfabric import ClosureState, WorkOperation, WorkState
from src.storage.postgres.bounded_work_batch import (
    claim_work_batch,
    release_unstarted_leases,
)
from src.storage.postgres.numeric_hyperfabric_store import WorkLease
from src.storage.postgres.spacy_parser_model import connect


_DEFAULT_LEASE_BATCH_SIZE = 16


@dataclass(frozen=True, slots=True)
class AdjacentReconciliationSummary:
    completed_pairs: int
    last_pair_interface_id: int | None


def execute_adjacent_lease(cursor: Any, lease: WorkLease) -> int:
    """Execute one already-leased adjacent pair through the SQL fence."""

    if lease.operation is not WorkOperation.ADJACENT_RECONCILE:
        raise ValueError("adjacent executor requires an adjacent-reconcile lease")
    cursor.execute(
        """
        SELECT execution.execute_numeric_pnf_adjacent_work(%s, %s, %s)
        """,
        (lease.work_id, lease.lease_token, lease.lease_epoch),
    )
    row = cursor.fetchone()
    if row is None or row[0] is None:
        raise RuntimeError("adjacent reconciliation returned no pair interface")
    return int(row[0])


def _fail_adjacent_lease(cursor: Any, lease: WorkLease) -> None:
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_work_item
           SET state_id = %s,
               lease_owner = NULL,
               lease_token = NULL,
               lease_expires_at = NULL,
               completed_at = CURRENT_TIMESTAMP,
               last_error_code = 2
         WHERE work_id = %s
           AND state_id = %s
           AND lease_token = %s
           AND lease_epoch = %s
        """,
        (
            int(WorkState.FAILED),
            lease.work_id,
            int(WorkState.LEASED),
            lease.lease_token,
            lease.lease_epoch,
        ),
    )
    cursor.execute(
        """
        UPDATE execution.semantic_pnf_region
           SET closure_state = %s
         WHERE region_id = %s
           AND closure_state = %s
        """,
        (
            int(ClosureState.FAILED),
            lease.region_id,
            int(ClosureState.OPEN),
        ),
    )


def drain_adjacent_reconciliation(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    lease_batch_size: int = _DEFAULT_LEASE_BATCH_SIZE,
) -> AdjacentReconciliationSummary:
    """Lease and close up to ``limit`` adjacent fibres.

    Lease acquisition is batched, but execution remains one exact adjacent fibre
    per existing semantic transaction.  This deliberately does *not* assert
    that neighbouring braid obligations commute.  If execution fails while a
    batch still contains unstarted leases, those exact lease tokens/epochs are
    returned to READY before the error is propagated.
    """

    if limit < 1:
        raise ValueError("adjacent reconciliation limit must be positive")
    if lease_batch_size < 1:
        raise ValueError("adjacent lease batch size must be positive")

    completed = 0
    last_interface_id: int | None = None
    connection = connect(database_url)
    try:
        while completed < limit:
            remaining = limit - completed
            with connection.transaction():
                with connection.cursor() as cursor:
                    leases = claim_work_batch(
                        cursor,
                        run_ref=run_ref,
                        worker_ref=worker_ref,
                        operation=WorkOperation.ADJACENT_RECONCILE,
                        limit=min(lease_batch_size, remaining),
                    )
            if not leases:
                break

            for index, lease in enumerate(leases):
                try:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            last_interface_id = execute_adjacent_lease(cursor, lease)
                    completed += 1
                except BaseException:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            _fail_adjacent_lease(cursor, lease)
                            release_unstarted_leases(cursor, leases[index + 1 :])
                    raise
    finally:
        connection.close()

    return AdjacentReconciliationSummary(
        completed_pairs=completed,
        last_pair_interface_id=last_interface_id,
    )


__all__ = [
    "AdjacentReconciliationSummary",
    "drain_adjacent_reconciliation",
    "execute_adjacent_lease",
]
