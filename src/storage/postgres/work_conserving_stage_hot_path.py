"""Cheaper exact completion and execution for work-conserving COPY stages.

Each partition writes its COPY rows and its `document_persistence_lane` staged
receipt in the same committed PostgreSQL transaction. Consequently a complete
set of staged lane receipts whose row counts sum to the declared run row count
is an exact publication precondition; rescanning every provisional row merely to
COUNT them is redundant I/O.

Physical stage execution reuses one bounded thread executor and reusable
PostgreSQL transaction leases. Published provisional rows are execution-only,
UNLOGGED, and keyed by deterministic stage refs, so their deletion is amortized
across documents rather than doubling row/index churn in every authority commit.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
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
_CLEANUP_LOCK = Lock()
_COMPLETED_DOCUMENTS = 0


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


def _cleanup_interval() -> int:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_CLEANUP_EVERY_DOCUMENTS", "16")
    value = int(raw)
    if value < 0:
        raise ValueError(
            "SENSIBLAW_PERSISTENCE_CLEANUP_EVERY_DOCUMENTS must be non-negative"
        )
    return value


def _maybe_cleanup_published_stages(runtime: Any) -> None:
    """Amortize deletion of execution-only rows after successful publication.

    A value of 0 disables opportunistic cleanup entirely. Deterministic stage
    setup still deletes rows for its own stage_ref before replay, so disabling
    the sweep changes only retained execution storage, never semantic results.
    """

    global _COMPLETED_DOCUMENTS
    interval = _cleanup_interval()
    if interval == 0 or runtime.dsn is None:
        return
    with _CLEANUP_LOCK:
        _COMPLETED_DOCUMENTS += 1
        if _COMPLETED_DOCUMENTS % interval:
            return
        dsn = runtime.dsn
    # Delete only rows whose authority publication committed. Staged/failed rows
    # remain for recovery and diagnostics. One set operation amortizes cleanup
    # over the preceding document epoch.
    with transactional_persistence_connection(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM execution.document_persistence_stage AS staged
                USING execution.document_persistence_run AS run
                WHERE run.stage_ref = staged.stage_ref
                  AND run.state_ref = 'published'
                """
            )


def install_work_conserving_stage_hot_path() -> bool:
    from src.storage.postgres import work_conserving_stage as stage

    if getattr(stage, _INSTALL_MARKER, False):
        return False

    original_runtime_finish = stage.DocumentPersistenceRuntime.finish

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
        # so COPY workers can observe the run row and clean any same-stage replay.
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

    def complete_stage(cursor: Any, *, stage_ref: str, statement_count: int) -> None:
        # Do not delete provisional rows in the authority transaction. Marking
        # the execution receipt published is enough; cleanup occurs only after
        # the document savepoint has committed and is amortized across documents.
        cursor.execute(
            """
            UPDATE execution.document_persistence_run
            SET state_ref = 'published', statement_count = %s,
                published_at = CURRENT_TIMESTAMP
            WHERE stage_ref = %s
            """,
            (statement_count, stage_ref),
        )

    def runtime_finish(self: Any) -> None:
        # `finish()` is reached after persist_document_compilation returns, hence
        # after the ordered document savepoint commit. Querying only published
        # runs makes this safe even when the savepoint raised and rolled back.
        try:
            _maybe_cleanup_published_stages(self)
        finally:
            original_runtime_finish(self)

    stage._prepare_stage = prepare_stage
    stage._stage_payloads = stage_payloads
    stage._complete_stage = complete_stage
    stage.DocumentPersistenceRuntime.finish = runtime_finish
    setattr(stage, _INSTALL_MARKER, True)
    return True


__all__ = ["install_work_conserving_stage_hot_path"]
