"""Fenced execution of overlapping adjacent-region PNF fibres."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.pnf.numeric_hyperfabric import ClosureState, WorkOperation, WorkState
from src.storage.postgres.numeric_hyperfabric_store import WorkLease, claim_work
from src.storage.postgres.spacy_parser_model import connect


@dataclass(frozen=True, slots=True)
class AdjacentReconciliationSummary:
    completed_pairs: int
    last_pair_interface_id: int | None
    completed_pair_interface_ids: tuple[int, ...] = ()


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
) -> AdjacentReconciliationSummary:
    """Lease and close up to ``limit`` adjacent sentence/paragraph fibres."""

    if limit < 1:
        raise ValueError("adjacent reconciliation limit must be positive")

    completed = 0
    last_interface_id: int | None = None
    completed_interface_ids: list[int] = []
    connection = connect(database_url)
    try:
        while completed < limit:
            with connection.transaction():
                with connection.cursor() as cursor:
                    lease = claim_work(
                        cursor,
                        run_ref=run_ref,
                        worker_ref=worker_ref,
                        operation=WorkOperation.ADJACENT_RECONCILE,
                    )
            if lease is None:
                break

            try:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        last_interface_id = execute_adjacent_lease(cursor, lease)
                completed_interface_ids.append(last_interface_id)
                completed += 1
            except BaseException:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        _fail_adjacent_lease(cursor, lease)
                raise
    finally:
        connection.close()

    return AdjacentReconciliationSummary(
        completed_pairs=completed,
        last_pair_interface_id=last_interface_id,
        completed_pair_interface_ids=tuple(completed_interface_ids),
    )


__all__ = [
    "AdjacentReconciliationSummary",
    "drain_adjacent_reconciliation",
    "execute_adjacent_lease",
]
