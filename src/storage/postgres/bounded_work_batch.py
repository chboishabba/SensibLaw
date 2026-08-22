"""Bounded set-wise leasing for exact PNF work fibres.

The semantic work item remains the unit of authority, retry and failure.  This
module changes only the physical queue transition:

    N x (claim one -> commit)
        becomes
    claim <= k exact work fibres -> one fenced lease update -> commit.

Execution of each returned :class:`WorkLease` remains individually fenced by the
existing sentence/adjacent executors.  Nothing here asserts that neighbouring
fibres commute, join, or may share a semantic transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from src.pnf.numeric_hyperfabric import WorkOperation, WorkState
from src.storage.postgres.numeric_hyperfabric_store import WorkLease


@dataclass(frozen=True, slots=True)
class WorkBatchLeaseReceipt:
    semantic_fibres: int
    claim_select_statements: int
    claim_update_statements: int
    claim_transactions: int

    @property
    def orchestration_statements(self) -> int:
        return self.claim_select_statements + self.claim_update_statements


def claim_work_batch(
    cursor: Any,
    *,
    run_ref: str,
    worker_ref: str,
    operation: WorkOperation,
    limit: int,
    lease_seconds: int = 120,
) -> tuple[WorkLease, ...]:
    """Lease a bounded ordered fibre with one select and one fenced update.

    The caller owns the surrounding transaction.  Selection keeps the existing
    priority/work-id order and ``SKIP LOCKED`` semantics; every returned row gets
    its own token and incremented epoch, so downstream execution retains the
    same per-work-item fence as the singleton path.
    """

    if limit < 1:
        raise ValueError("numeric PNF work batch limit must be positive")
    if lease_seconds < 1:
        raise ValueError("numeric PNF work lease must be positive")

    cursor.execute(
        """
        SELECT work_id, region_id, lease_epoch
          FROM execution.semantic_pnf_work_item
         WHERE run_ref = %s
           AND operation_id = %s
           AND (
               state_id = %s
               OR (
                   state_id = %s
                   AND lease_expires_at < CURRENT_TIMESTAMP
               )
           )
         ORDER BY priority, work_id
         FOR UPDATE SKIP LOCKED
         LIMIT %s
        """,
        (
            run_ref,
            int(operation),
            int(WorkState.READY),
            int(WorkState.LEASED),
            limit,
        ),
    )
    rows = tuple(cursor.fetchall())
    if not rows:
        return ()

    leases = tuple(
        WorkLease(
            work_id=int(work_id),
            region_id=int(region_id),
            operation=operation,
            lease_token=uuid4().hex,
            lease_epoch=int(prior_epoch) + 1,
        )
        for work_id, region_id, prior_epoch in rows
    )
    work_ids = [lease.work_id for lease in leases]
    lease_tokens = [lease.lease_token for lease in leases]
    lease_epochs = [lease.lease_epoch for lease in leases]

    cursor.execute(
        """
        WITH leased(work_id, lease_token, lease_epoch) AS (
            SELECT *
              FROM unnest(%s::BIGINT[], %s::TEXT[], %s::BIGINT[])
        )
        UPDATE execution.semantic_pnf_work_item AS work
           SET state_id = %s,
               lease_owner = %s,
               lease_token = leased.lease_token,
               lease_epoch = leased.lease_epoch,
               lease_expires_at = CURRENT_TIMESTAMP
                   + (%s * INTERVAL '1 second'),
               attempt_count = work.attempt_count + 1
          FROM leased
         WHERE work.work_id = leased.work_id
        """,
        (
            work_ids,
            lease_tokens,
            lease_epochs,
            int(WorkState.LEASED),
            worker_ref,
            lease_seconds,
        ),
    )
    if cursor.rowcount != len(leases):
        raise RuntimeError("numeric PNF batch lease fence changed during claim")
    return leases


def release_unstarted_leases(cursor: Any, leases: tuple[WorkLease, ...]) -> int:
    """Return exact not-yet-started leases to READY after an in-process failure.

    Process death remains covered by ordinary lease expiry.  This helper is for
    the stronger case where the batching process is alive and knows which
    already-claimed fibres it did not execute.
    """

    if not leases:
        return 0
    work_ids = [lease.work_id for lease in leases]
    lease_tokens = [lease.lease_token for lease in leases]
    lease_epochs = [lease.lease_epoch for lease in leases]
    cursor.execute(
        """
        WITH abandoned(work_id, lease_token, lease_epoch) AS (
            SELECT *
              FROM unnest(%s::BIGINT[], %s::TEXT[], %s::BIGINT[])
        )
        UPDATE execution.semantic_pnf_work_item AS work
           SET state_id = %s,
               lease_owner = NULL,
               lease_token = NULL,
               lease_expires_at = NULL
          FROM abandoned
         WHERE work.work_id = abandoned.work_id
           AND work.state_id = %s
           AND work.lease_token = abandoned.lease_token
           AND work.lease_epoch = abandoned.lease_epoch
        """,
        (
            work_ids,
            lease_tokens,
            lease_epochs,
            int(WorkState.READY),
            int(WorkState.LEASED),
        ),
    )
    return int(cursor.rowcount)


__all__ = [
    "WorkBatchLeaseReceipt",
    "claim_work_batch",
    "release_unstarted_leases",
]
