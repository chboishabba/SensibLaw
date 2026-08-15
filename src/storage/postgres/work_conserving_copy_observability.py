"""Live-visible COPY lanes for work-conserving PostgreSQL persistence."""

from __future__ import annotations

import os
import resource
from time import monotonic_ns
from typing import Any, Sequence

from src.storage.postgres import work_conserving_stage as stage


def _record_lane_started(
    *,
    dsn: str,
    stage_ref: str,
    lane_ref: str,
    partition_no: int,
    backend_pid: int,
    row_count: int,
    byte_count: int,
) -> None:
    psycopg = stage._require_psycopg()
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO execution.document_persistence_lane
                    (stage_ref, lane_ref, partition_no, state_ref,
                     backend_pid, worker_pid, row_count, byte_count,
                     started_at)
                VALUES (%s, %s, %s, 'staging', %s, %s, %s, %s,
                        CURRENT_TIMESTAMP)
                ON CONFLICT (stage_ref, lane_ref, partition_no) DO UPDATE SET
                    state_ref = 'staging',
                    backend_pid = EXCLUDED.backend_pid,
                    worker_pid = EXCLUDED.worker_pid,
                    row_count = EXCLUDED.row_count,
                    byte_count = EXCLUDED.byte_count,
                    elapsed_ms = 0,
                    client_user_cpu_ms = 0,
                    client_system_cpu_ms = 0,
                    wait_event_type_ref = NULL,
                    wait_event_ref = NULL,
                    started_at = CURRENT_TIMESTAMP,
                    completed_at = NULL
                """,
                (
                    stage_ref,
                    lane_ref,
                    partition_no,
                    backend_pid,
                    os.getpid(),
                    row_count,
                    byte_count,
                ),
            )


def _record_lane_failed(
    *,
    dsn: str,
    stage_ref: str,
    lane_ref: str,
    partition_no: int,
    elapsed_ms: int,
) -> None:
    psycopg = stage._require_psycopg()
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE execution.document_persistence_lane
                SET state_ref = 'failed', elapsed_ms = %s,
                    completed_at = CURRENT_TIMESTAMP
                WHERE stage_ref = %s AND lane_ref = %s AND partition_no = %s
                """,
                (elapsed_ms, stage_ref, lane_ref, partition_no),
            )


def observable_stage_partition(
    *,
    dsn: str,
    stage_ref: str,
    lane_ref: str,
    partition_no: int,
    rows: Sequence[tuple[Any, ...]],
) -> dict[str, Any]:
    """COPY one partition while exposing its backend PID before work begins."""

    psycopg = stage._require_psycopg()
    started_ns = monotonic_ns()
    before = resource.getrusage(resource.RUSAGE_THREAD)
    backend_pid: int | None = None
    byte_count = sum(stage._estimate_row_bytes(row) for row in rows)
    try:
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid = int(cursor.fetchone()[0])
                _record_lane_started(
                    dsn=dsn,
                    stage_ref=stage_ref,
                    lane_ref=lane_ref,
                    partition_no=partition_no,
                    backend_pid=backend_pid,
                    row_count=len(rows),
                    byte_count=byte_count,
                )
                with cursor.copy(stage._COPY_SQL) as copy:
                    for row in rows:
                        copy.write_row(row)
                cursor.execute(
                    """
                    SELECT wait_event_type, wait_event
                    FROM pg_stat_activity
                    WHERE pid = pg_backend_pid()
                    """
                )
                wait_row = cursor.fetchone()
                wait_type = wait_row[0] if wait_row is not None else None
                wait_event = wait_row[1] if wait_row is not None else None
                after = resource.getrusage(resource.RUSAGE_THREAD)
                elapsed_ms = max(0, (monotonic_ns() - started_ns) // 1_000_000)
                user_ms = max(0, int((after.ru_utime - before.ru_utime) * 1000))
                system_ms = max(0, int((after.ru_stime - before.ru_stime) * 1000))
                cursor.execute(
                    """
                    UPDATE execution.document_persistence_lane
                    SET state_ref = 'staged', backend_pid = %s,
                        worker_pid = %s, row_count = %s, byte_count = %s,
                        elapsed_ms = %s, client_user_cpu_ms = %s,
                        client_system_cpu_ms = %s,
                        wait_event_type_ref = %s, wait_event_ref = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE stage_ref = %s AND lane_ref = %s
                      AND partition_no = %s
                    """,
                    (
                        backend_pid,
                        os.getpid(),
                        len(rows),
                        byte_count,
                        elapsed_ms,
                        user_ms,
                        system_ms,
                        wait_type,
                        wait_event,
                        stage_ref,
                        lane_ref,
                        partition_no,
                    ),
                )
    except BaseException:
        try:
            _record_lane_failed(
                dsn=dsn,
                stage_ref=stage_ref,
                lane_ref=lane_ref,
                partition_no=partition_no,
                elapsed_ms=max(0, (monotonic_ns() - started_ns) // 1_000_000),
            )
        except Exception:
            pass
        raise
    return {
        "partition_no": partition_no,
        "backend_pid": backend_pid,
        "row_count": len(rows),
        "byte_count": byte_count,
        "elapsed_ms": max(0, (monotonic_ns() - started_ns) // 1_000_000),
    }


def observable_stage_payloads(
    cursor: Any,
    *,
    family_ref: str,
    lane_ref: str,
    payloads: Sequence[stage.StagePayload],
) -> str:
    """Stage a family, then expose the authority-merge leader PID."""

    stage_ref = stage._stage_payloads(
        cursor,
        family_ref=family_ref,
        lane_ref=lane_ref,
        payloads=payloads,
    )
    dsn = str(cursor.connection.info.dsn)
    cursor.execute("SELECT pg_backend_pid()")
    backend_pid = int(cursor.fetchone()[0])
    psycopg = stage._require_psycopg()
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as telemetry:
            telemetry.execute(
                """
                INSERT INTO execution.document_persistence_lane
                    (stage_ref, lane_ref, partition_no, state_ref,
                     backend_pid, worker_pid, row_count, byte_count,
                     started_at)
                VALUES (%s, 'authority', 0, 'staging', %s, %s, %s, 0,
                        CURRENT_TIMESTAMP)
                ON CONFLICT (stage_ref, lane_ref, partition_no) DO UPDATE SET
                    state_ref = 'staging',
                    backend_pid = EXCLUDED.backend_pid,
                    worker_pid = EXCLUDED.worker_pid,
                    row_count = EXCLUDED.row_count,
                    byte_count = 0,
                    elapsed_ms = 0,
                    client_user_cpu_ms = 0,
                    client_system_cpu_ms = 0,
                    wait_event_type_ref = NULL,
                    wait_event_ref = NULL,
                    started_at = CURRENT_TIMESTAMP,
                    completed_at = NULL
                """,
                (stage_ref, backend_pid, os.getpid(), len(payloads)),
            )
    return stage_ref


def observable_complete_stage(
    cursor: Any,
    *,
    stage_ref: str,
    statement_count: int,
) -> None:
    """Complete authority merge and close its externally visible lane."""

    stage._complete_stage(
        cursor,
        stage_ref=stage_ref,
        statement_count=statement_count,
    )
    dsn = str(cursor.connection.info.dsn)
    psycopg = stage._require_psycopg()
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as telemetry:
            telemetry.execute(
                """
                UPDATE execution.document_persistence_lane
                SET state_ref = 'staged',
                    elapsed_ms = GREATEST(
                        0,
                        FLOOR(EXTRACT(EPOCH FROM
                            (CURRENT_TIMESTAMP - started_at)) * 1000)::bigint
                    ),
                    completed_at = CURRENT_TIMESTAMP
                WHERE stage_ref = %s AND lane_ref = 'authority'
                  AND partition_no = 0
                """,
                (stage_ref,),
            )


__all__ = [
    "observable_complete_stage",
    "observable_stage_partition",
    "observable_stage_payloads",
]
