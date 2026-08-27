"""Fenced execution of overlapping adjacent-region PNF fibres.

E1 keeps the existing SQL pair executor as the semantic authority but changes
its physical dispatch shape. A bounded ordered lease tranche is claimed and
executed inside one PostgreSQL transaction. The server evaluates the existing
pair executor as an explicit recursive sequential fold, so batching does not
assert that neighbouring adjacent pairs commute or may resolve one another.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from src.pnf.numeric_hyperfabric import WorkOperation
from src.storage.postgres.bounded_work_batch import claim_work_batch
from src.storage.postgres.numeric_hyperfabric_store import WorkLease
from src.storage.postgres.spacy_parser_model import connect


_DEFAULT_LEASE_BATCH_SIZE = 64


@dataclass(frozen=True, slots=True)
class AdjacentReconciliationSummary:
    completed_pairs: int
    last_pair_interface_id: int | None
    tranche_count: int = 0
    lease_batch_count: int = 0
    server_dispatch_statement_count: int = 0
    authority_transaction_count: int = 0
    per_pair_client_round_trip_count: int = 0
    per_pair_commit_count: int = 0


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


def execute_adjacent_lease_tranche(
    cursor: Any,
    leases: Sequence[WorkLease],
) -> tuple[int, ...]:
    """Execute an ordered lease tranche in one server statement.

    The recursive CTE deliberately creates a data dependency from ordinal i to
    ordinal i+1. This is an exact sequential fold over the existing fenced SQL
    executor, not a claim that adjacent pairs commute. Every executor call runs
    inside the caller's transaction, so a failure rolls back the entire tranche,
    including its lease transition and any earlier pair publication.
    """

    leases = tuple(leases)
    if not leases:
        return ()
    if any(lease.operation is not WorkOperation.ADJACENT_RECONCILE for lease in leases):
        raise ValueError("adjacent tranche requires adjacent-reconcile leases")

    cursor.execute(
        """
        WITH RECURSIVE input(work_id, lease_token, lease_epoch, ordinal) AS (
            SELECT work_id, lease_token, lease_epoch, ordinal
              FROM unnest(%s::BIGINT[], %s::TEXT[], %s::BIGINT[])
                   WITH ORDINALITY
                   AS leased(work_id, lease_token, lease_epoch, ordinal)
        ),
        executed(ordinal, interface_id) AS (
            SELECT input.ordinal,
                   execution.execute_numeric_pnf_adjacent_work(
                       input.work_id,
                       input.lease_token,
                       input.lease_epoch
                   )
              FROM input
             WHERE input.ordinal = 1
            UNION ALL
            SELECT input.ordinal,
                   execution.execute_numeric_pnf_adjacent_work(
                       input.work_id,
                       input.lease_token,
                       input.lease_epoch
                   )
              FROM executed AS prior
              JOIN input
                ON input.ordinal = prior.ordinal + 1
        )
        SELECT ordinal, interface_id
          FROM executed
         ORDER BY ordinal
        """,
        (
            [lease.work_id for lease in leases],
            [lease.lease_token for lease in leases],
            [lease.lease_epoch for lease in leases],
        ),
    )
    rows = tuple(cursor.fetchall())
    if len(rows) != len(leases):
        raise RuntimeError(
            "adjacent tranche returned an incomplete ordered executor result"
        )
    expected_ordinals = tuple(range(1, len(leases) + 1))
    actual_ordinals = tuple(int(row[0]) for row in rows)
    if actual_ordinals != expected_ordinals:
        raise RuntimeError("adjacent tranche executor order changed")
    interface_ids = tuple(int(row[1]) for row in rows if row[1] is not None)
    if len(interface_ids) != len(leases):
        raise RuntimeError("adjacent tranche returned a null pair interface")
    return interface_ids


def drain_adjacent_reconciliation(
    database_url: str,
    *,
    run_ref: str,
    worker_ref: str,
    limit: int = 64,
    lease_batch_size: int = _DEFAULT_LEASE_BATCH_SIZE,
) -> AdjacentReconciliationSummary:
    """Lease and close up to ``limit`` adjacent fibres in ordered tranches.

    Claim and execution share one transaction per tranche. Pair semantics remain
    exactly those of ``execute_numeric_pnf_adjacent_work`` and are evaluated in
    lease order on the server. There is no per-pair client round trip or commit.
    A failed tranche publishes no successful prefix: PostgreSQL rollback restores
    both the batch leases and every pair mutation before the exception escapes.
    """

    if limit < 1:
        raise ValueError("adjacent reconciliation limit must be positive")
    if lease_batch_size < 1:
        raise ValueError("adjacent lease batch size must be positive")

    completed = 0
    last_interface_id: int | None = None
    tranche_count = 0
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
                    interface_ids = execute_adjacent_lease_tranche(cursor, leases)
                    last_interface_id = interface_ids[-1]
                    completed += len(interface_ids)
                    tranche_count += 1
    finally:
        connection.close()

    return AdjacentReconciliationSummary(
        completed_pairs=completed,
        last_pair_interface_id=last_interface_id,
        tranche_count=tranche_count,
        lease_batch_count=tranche_count,
        server_dispatch_statement_count=tranche_count,
        authority_transaction_count=tranche_count,
        per_pair_client_round_trip_count=0,
        per_pair_commit_count=0,
    )


__all__ = [
    "AdjacentReconciliationSummary",
    "drain_adjacent_reconciliation",
    "execute_adjacent_lease",
    "execute_adjacent_lease_tranche",
]
