"""Cheaper exact completion and execution for work-conserving COPY stages.

Each partition writes its COPY rows and its `document_persistence_lane` staged
receipt in the same committed PostgreSQL transaction.  Consequently a complete
set of staged lane receipts whose row counts sum to the declared run row count
is an exact publication precondition; rescanning every provisional row merely to
COUNT them is redundant I/O.

Physical stage execution also reuses one bounded thread executor and reusable
PostgreSQL transaction leases instead of constructing a new executor and backend
set for every persistence family.  Publication remains in the caller's ordered
document savepoint.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Sequence

from src.storage.postgres.reusable_persistence_connections import (
    persistence_telemetry_cursor,
    transactional_persistence_connection,
)


_INSTALL_MARKER = "_work_conserving_stage_hot_path_installed"
_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_WORKERS = 0
_EXECUTOR_LOCK = Lock()


def _executor(worker_count: int) -> ThreadPoolExecutor:
    global _EXECUTOR, _EXECUTOR_WORKERS
    workers = max(1, worker_count)
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="pg-stage",
            )
            _EXECUTOR_WORKERS = workers
        elif _EXECUTOR_WORKERS < workers:
            # Persistence families for one ordered document are staged
            # sequentially, so growing the pool at a family boundary is safe.
            prior = _EXECUTOR
            _EXECUTOR = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="pg-stage",
            )
            _EXECUTOR_WORKERS = workers
            prior.shutdown(wait=True, cancel_futures=False)
        return _EXECUTOR


def install_work_conserving_stage_hot_path() -> bool:
    from src.storage.postgres import work_conserving_stage as stage

    if getattr(stage, _INSTALL_MARKER, False):
        return False

    def prepare_stage(
        *,
        dsn: str,
        stage_ref: str,
        document_ref: str,
        build_key_sha256: str,
        family_ref: str,
        lane_ref: str,
        payloads: Sequence[Any],
        worker_budget: int,
    ) -> tuple[dict[str, Any], ...]:
        worker_count = min(max(1, worker_budget), max(1, len(payloads)))
        partitions: list[list[tuple[Any, ...]]] = [[] for _ in range(worker_count)]
        for ordinal, payload in enumerate(payloads):
            partition_no = ordinal % worker_count
            partitions[partition_no].append(
                payload.copy_row(
                    stage_ref=stage_ref,
                    document_ref=document_ref,
                    build_key_sha256=build_key_sha256,
                    lane_ref=lane_ref,
                    partition_no=partition_no,
                    ordinal=ordinal,
                )
            )

        # Setup is its own committed execution transaction, exactly as before,
        # so COPY workers can observe the run row and clean staging surface.
        with transactional_persistence_connection(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM execution.document_persistence_lane WHERE stage_ref = %s",
                    (stage_ref,),
                )
                cursor.execute(
                    "DELETE FROM execution.document_persistence_stage WHERE stage_ref = %s",
                    (stage_ref,),
                )
                cursor.execute(
                    """
                    INSERT INTO execution.document_persistence_run
                        (stage_ref, document_ref, build_key_sha256, family_ref,
                         state_ref, worker_budget, lane_count, row_count,
                         statement_count, started_at, staged_at, published_at,
                         failure_type_ref, failure_message)
                    VALUES (%s, %s, %s, %s, 'staging', %s, 0, 0, 0,
                            CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL)
                    ON CONFLICT (stage_ref) DO UPDATE SET
                        state_ref = 'staging',
                        worker_budget = EXCLUDED.worker_budget,
                        lane_count = 0,
                        row_count = 0,
                        statement_count = 0,
                        started_at = CURRENT_TIMESTAMP,
                        staged_at = NULL,
                        published_at = NULL,
                        failure_type_ref = NULL,
                        failure_message = NULL
                    """,
                    (
                        stage_ref,
                        document_ref,
                        build_key_sha256,
                        family_ref,
                        worker_budget,
                    ),
                )

        results: list[dict[str, Any]] = []
        nonempty = [(index, rows) for index, rows in enumerate(partitions) if rows]
        try:
            executor = _executor(max(1, len(nonempty)))
            futures = {
                executor.submit(
                    stage._stage_partition,
                    dsn=dsn,
                    stage_ref=stage_ref,
                    lane_ref=lane_ref,
                    partition_no=index,
                    rows=rows,
                ): index
                for index, rows in nonempty
            }
            for future in as_completed(futures):
                results.append(future.result())
        except BaseException as error:
            # Failure telemetry is independent and immediately visible; it must
            # not wait for or consume a transactional COPY pool lease.
            with persistence_telemetry_cursor(dsn) as cursor:
                cursor.execute(
                    """
                    UPDATE execution.document_persistence_run
                    SET state_ref = 'failed', failure_type_ref = %s,
                        failure_message = %s
                    WHERE stage_ref = %s
                    """,
                    (type(error).__name__, str(error), stage_ref),
                )
            raise

        with transactional_persistence_connection(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.document_persistence_run
                    SET state_ref = 'staged', lane_count = %s, row_count = %s,
                        staged_at = CURRENT_TIMESTAMP
                    WHERE stage_ref = %s
                    """,
                    (len(results), len(payloads), stage_ref),
                )
        return tuple(sorted(results, key=lambda row: int(row["partition_no"])))

    def stage_payloads(
        cursor: Any,
        *,
        family_ref: str,
        lane_ref: str,
        payloads: Sequence[Any],
    ) -> str:
        runtime = stage._runtime()
        stage_ref = runtime.stage_ref(family_ref)
        try:
            dsn = str(cursor.connection.info.dsn)
        except AttributeError as error:  # pragma: no cover - compatibility seam
            raise RuntimeError(
                "PostgreSQL cursor does not expose a reusable DSN"
            ) from error
        runtime.register_stage(stage_ref=stage_ref, dsn=dsn)
        stage._prepare_stage(
            dsn=dsn,
            stage_ref=stage_ref,
            document_ref=runtime.document_ref,
            build_key_sha256=runtime.build_key_sha256,
            family_ref=family_ref,
            lane_ref=lane_ref,
            payloads=payloads,
            worker_budget=runtime.worker_budget,
        )

        # COPY and the corresponding staged lane receipt commit atomically on
        # each partition connection. Prove complete coverage from that compact
        # ledger instead of scanning the provisional row table again.
        cursor.execute(
            """
            SELECT run.row_count,
                   run.lane_count,
                   COALESCE(SUM(lane.row_count), 0),
                   COUNT(lane.partition_no)
            FROM execution.document_persistence_run AS run
            LEFT JOIN execution.document_persistence_lane AS lane
              ON lane.stage_ref = run.stage_ref
             AND lane.lane_ref = %s
             AND lane.state_ref = 'staged'
            WHERE run.stage_ref = %s AND run.state_ref = 'staged'
            GROUP BY run.row_count, run.lane_count
            """,
            (lane_ref, stage_ref),
        )
        completeness = cursor.fetchone()
        if completeness is None:
            raise RuntimeError(
                "provisional persistence stage is incomplete before authority merge"
            )
        expected_rows, expected_lanes, staged_rows, staged_lanes = map(
            int, completeness
        )
        if expected_rows != staged_rows or expected_lanes != staged_lanes:
            raise RuntimeError(
                "provisional persistence lane ledger is incomplete before authority merge: "
                f"expected_rows={expected_rows} staged_rows={staged_rows} "
                f"expected_lanes={expected_lanes} staged_lanes={staged_lanes}"
            )

        connection_id = id(cursor.connection)
        verified = getattr(runtime, "_verified_publication_connections", None)
        if verified is None:
            verified = set()
            setattr(runtime, "_verified_publication_connections", verified)
        if connection_id not in verified:
            cursor.execute("SHOW transaction_isolation")
            isolation = str(cursor.fetchone()[0]).casefold().replace(" ", "_")
            if isolation != "read_committed":
                raise RuntimeError(
                    "parallel provisional staging requires READ COMMITTED visibility; "
                    f"observed={isolation}"
                )
            cursor.execute(
                "SELECT set_config('max_parallel_workers_per_gather', %s, true)",
                (str(runtime.worker_budget),),
            )
            verified.add(connection_id)

        cursor.execute(
            """
            UPDATE execution.document_persistence_run
            SET state_ref = 'publishing'
            WHERE stage_ref = %s AND state_ref = 'staged'
            """,
            (stage_ref,),
        )
        return stage_ref

    stage._prepare_stage = prepare_stage
    stage._stage_payloads = stage_payloads
    setattr(stage, _INSTALL_MARKER, True)
    return True


__all__ = ["install_work_conserving_stage_hot_path"]
