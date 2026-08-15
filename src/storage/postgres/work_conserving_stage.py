"""Typed execution-only staging and worker-budget runtime."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import os
import resource
from threading import Lock
from time import monotonic_ns
from typing import Any, Callable, Iterator, Sequence

from src.policy.carriers.canonical import canonical_sha256


WORK_CONSERVING_PERSISTENCE_CONTRACT = "work-conserving-postgres-persistence:v0_1"
_STAGE_COLUMNS = (
    "stage_ref",
    "document_ref",
    "build_key_sha256",
    "lane_ref",
    "row_kind_ref",
    "partition_no",
    "ordinal",
    *(f"text_{index:02d}" for index in range(1, 13)),
    *(f"int_{index:02d}" for index in range(1, 7)),
    "bytea_01",
    "bytea_02",
)
_COPY_SQL = (
    "COPY execution.document_persistence_stage ("
    + ", ".join(_STAGE_COLUMNS)
    + ") FROM STDIN"
)


def _sha(value: object) -> bytes:
    return bytes.fromhex(canonical_sha256(value))


def _text_sha(value: object) -> str:
    return canonical_sha256(value)


@dataclass(frozen=True)
class StagePayload:
    """One typed provisional row before execution coordinates are attached."""

    row_kind_ref: str
    texts: tuple[str | None, ...] = ()
    ints: tuple[int | None, ...] = ()
    byteas: tuple[bytes | None, ...] = ()

    def __post_init__(self) -> None:
        if not self.row_kind_ref:
            raise ValueError("row_kind_ref is required")
        if len(self.texts) > 12:
            raise ValueError("staged payload exceeds twelve text fields")
        if len(self.ints) > 6:
            raise ValueError("staged payload exceeds six integer fields")
        if len(self.byteas) > 2:
            raise ValueError("staged payload exceeds two bytea fields")

    def copy_row(
        self,
        *,
        stage_ref: str,
        document_ref: str,
        build_key_sha256: str,
        lane_ref: str,
        partition_no: int,
        ordinal: int,
    ) -> tuple[Any, ...]:
        return (
            stage_ref,
            document_ref,
            build_key_sha256,
            lane_ref,
            self.row_kind_ref,
            partition_no,
            ordinal,
            *self.texts,
            *(None for _ in range(12 - len(self.texts))),
            *self.ints,
            *(None for _ in range(6 - len(self.ints))),
            *self.byteas,
            *(None for _ in range(2 - len(self.byteas))),
        )


@dataclass(frozen=True)
class PersistenceRuntimeConfig:
    worker_budget: int
    before_persistence: Callable[[], None] | None = None
    after_persistence: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        if self.worker_budget < 1:
            raise ValueError("worker_budget must be positive")


@dataclass
class DocumentPersistenceRuntime:
    document_ref: str
    build_key_sha256: str
    config: PersistenceRuntimeConfig
    family_calls: dict[str, int] = field(default_factory=dict)
    stage_refs: list[str] = field(default_factory=list)
    dsn: str | None = None
    quiesced: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    @property
    def worker_budget(self) -> int:
        return self.config.worker_budget

    def ensure_budget(self) -> None:
        with self._lock:
            if self.quiesced:
                return
            if self.config.before_persistence is not None:
                self.config.before_persistence()
            self.quiesced = True

    def stage_ref(self, family_ref: str) -> str:
        with self._lock:
            call_no = self.family_calls.get(family_ref, 0)
            self.family_calls[family_ref] = call_no + 1
        return "document-persistence-stage:" + canonical_sha256(
            {
                "contract_ref": WORK_CONSERVING_PERSISTENCE_CONTRACT,
                "document_ref": self.document_ref,
                "build_key_sha256": self.build_key_sha256,
                "family_ref": family_ref,
                "call_no": call_no,
            }
        )

    def register_stage(self, *, stage_ref: str, dsn: str) -> None:
        with self._lock:
            if stage_ref not in self.stage_refs:
                self.stage_refs.append(stage_ref)
            if self.dsn is None:
                self.dsn = dsn
            elif self.dsn != dsn:
                raise RuntimeError(
                    "one document persistence runtime used multiple DSNs"
                )

    def fail(self, error: BaseException) -> None:
        with self._lock:
            dsn = self.dsn
            stage_refs = tuple(self.stage_refs)
        if dsn is None or not stage_refs:
            return
        psycopg = _require_psycopg()
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE execution.document_persistence_run
                    SET state_ref = 'failed', failure_type_ref = %s,
                        failure_message = %s
                    WHERE stage_ref = ANY(%s)
                      AND state_ref <> 'published'
                    """,
                    (type(error).__name__, str(error), list(stage_refs)),
                )

    def finish(self) -> None:
        with self._lock:
            should_resume = self.quiesced
            self.quiesced = False
        if should_resume and self.config.after_persistence is not None:
            self.config.after_persistence()


_CONFIG: ContextVar[PersistenceRuntimeConfig | None] = ContextVar(
    "work_conserving_persistence_config", default=None
)
_DOCUMENT_RUNTIME: ContextVar[DocumentPersistenceRuntime | None] = ContextVar(
    "work_conserving_document_persistence_runtime", default=None
)


@contextmanager
def configure_work_conserving_persistence(
    *,
    worker_budget: int,
    before_persistence: Callable[[], None] | None = None,
    after_persistence: Callable[[], None] | None = None,
) -> Iterator[None]:
    token = _CONFIG.set(
        PersistenceRuntimeConfig(
            worker_budget=worker_budget,
            before_persistence=before_persistence,
            after_persistence=after_persistence,
        )
    )
    try:
        yield
    finally:
        _CONFIG.reset(token)


@contextmanager
def document_persistence_runtime(
    *, document_ref: str, build_key_sha256: str
) -> Iterator[DocumentPersistenceRuntime]:
    config = _CONFIG.get()
    if config is None:
        configured = int(os.environ.get("SENSIBLAW_PERSISTENCE_WORKERS", "1"))
        config = PersistenceRuntimeConfig(worker_budget=max(1, configured))
    runtime = DocumentPersistenceRuntime(
        document_ref=document_ref,
        build_key_sha256=build_key_sha256,
        config=config,
    )
    token = _DOCUMENT_RUNTIME.set(runtime)
    try:
        yield runtime
    except BaseException as error:
        try:
            runtime.fail(error)
        except Exception:
            # Failure telemetry must never replace the document failure.
            pass
        raise
    finally:
        runtime.finish()
        _DOCUMENT_RUNTIME.reset(token)


def _runtime() -> DocumentPersistenceRuntime:
    runtime = _DOCUMENT_RUNTIME.get()
    if runtime is None:
        raise RuntimeError(
            "work-conserving persistence helper used outside document runtime"
        )
    runtime.ensure_budget()
    return runtime


def _estimate_row_bytes(row: Sequence[Any]) -> int:
    total = 0
    for value in row:
        if value is None:
            continue
        if isinstance(value, bytes):
            total += len(value)
        else:
            total += len(str(value).encode("utf-8"))
    return total


def _require_psycopg() -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "work-conserving persistence requires psycopg[binary]>=3.1"
        ) from error
    return psycopg


def _stage_partition(
    *,
    dsn: str,
    stage_ref: str,
    lane_ref: str,
    partition_no: int,
    rows: Sequence[tuple[Any, ...]],
) -> dict[str, Any]:
    psycopg = _require_psycopg()
    started_ns = monotonic_ns()
    before = resource.getrusage(resource.RUSAGE_THREAD)
    backend_pid: int | None = None
    wait_type: str | None = None
    wait_event: str | None = None
    byte_count = sum(_estimate_row_bytes(row) for row in rows)
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            backend_pid = int(cursor.fetchone()[0])
            with cursor.copy(_COPY_SQL) as copy:
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
            if wait_row is not None:
                wait_type = wait_row[0]
                wait_event = wait_row[1]
            after = resource.getrusage(resource.RUSAGE_THREAD)
            elapsed_ms = max(0, (monotonic_ns() - started_ns) // 1_000_000)
            user_ms = max(0, int((after.ru_utime - before.ru_utime) * 1000))
            system_ms = max(0, int((after.ru_stime - before.ru_stime) * 1000))
            cursor.execute(
                """
                INSERT INTO execution.document_persistence_lane
                    (stage_ref, lane_ref, partition_no, state_ref,
                     backend_pid, worker_pid, row_count, byte_count, elapsed_ms,
                     client_user_cpu_ms, client_system_cpu_ms,
                     wait_event_type_ref, wait_event_ref, completed_at)
                VALUES (%s, %s, %s, 'staged', %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (stage_ref, lane_ref, partition_no) DO UPDATE SET
                    state_ref = EXCLUDED.state_ref,
                    backend_pid = EXCLUDED.backend_pid,
                    worker_pid = EXCLUDED.worker_pid,
                    row_count = EXCLUDED.row_count,
                    byte_count = EXCLUDED.byte_count,
                    elapsed_ms = EXCLUDED.elapsed_ms,
                    client_user_cpu_ms = EXCLUDED.client_user_cpu_ms,
                    client_system_cpu_ms = EXCLUDED.client_system_cpu_ms,
                    wait_event_type_ref = EXCLUDED.wait_event_type_ref,
                    wait_event_ref = EXCLUDED.wait_event_ref,
                    completed_at = EXCLUDED.completed_at
                """,
                (
                    stage_ref,
                    lane_ref,
                    partition_no,
                    backend_pid,
                    os.getpid(),
                    len(rows),
                    byte_count,
                    elapsed_ms,
                    user_ms,
                    system_ms,
                    wait_type,
                    wait_event,
                ),
            )
    return {
        "partition_no": partition_no,
        "backend_pid": backend_pid,
        "row_count": len(rows),
        "byte_count": byte_count,
        "elapsed_ms": max(0, (monotonic_ns() - started_ns) // 1_000_000),
    }


def _prepare_stage(
    *,
    dsn: str,
    stage_ref: str,
    document_ref: str,
    build_key_sha256: str,
    family_ref: str,
    lane_ref: str,
    payloads: Sequence[StagePayload],
    worker_budget: int,
) -> tuple[dict[str, Any], ...]:
    psycopg = _require_psycopg()
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
    with psycopg.connect(dsn) as connection:
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
    nonempty = [rows for rows in partitions if rows]
    results: list[dict[str, Any]] = []
    try:
        with ThreadPoolExecutor(
            max_workers=max(1, len(nonempty)),
            thread_name_prefix=f"pg-stage-{lane_ref}",
        ) as executor:
            futures = {
                executor.submit(
                    _stage_partition,
                    dsn=dsn,
                    stage_ref=stage_ref,
                    lane_ref=lane_ref,
                    partition_no=index,
                    rows=rows,
                ): index
                for index, rows in enumerate(partitions)
                if rows
            }
            for future in as_completed(futures):
                results.append(future.result())
    except BaseException as error:
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
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
    with psycopg.connect(dsn) as connection:
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


def _stage_payloads(
    cursor: Any,
    *,
    family_ref: str,
    lane_ref: str,
    payloads: Sequence[StagePayload],
) -> str:
    runtime = _runtime()
    stage_ref = runtime.stage_ref(family_ref)
    try:
        dsn = str(cursor.connection.info.dsn)
    except AttributeError as error:  # pragma: no cover - compatibility seam
        raise RuntimeError(
            "PostgreSQL cursor does not expose a reusable DSN"
        ) from error
    runtime.register_stage(stage_ref=stage_ref, dsn=dsn)
    _prepare_stage(
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
        SELECT run.row_count, COUNT(stage.ordinal)
        FROM execution.document_persistence_run AS run
        LEFT JOIN execution.document_persistence_stage AS stage
          ON stage.stage_ref = run.stage_ref
        WHERE run.stage_ref = %s AND run.state_ref = 'staged'
        GROUP BY run.row_count
        """,
        (stage_ref,),
    )
    completeness = cursor.fetchone()
    if completeness is None or int(completeness[0]) != int(completeness[1]):
        raise RuntimeError(
            "provisional persistence stage is incomplete before authority merge"
        )
    cursor.execute("SHOW transaction_isolation")
    isolation = str(cursor.fetchone()[0]).casefold().replace(" ", "_")
    if isolation != "read_committed":
        raise RuntimeError(
            "parallel provisional staging requires READ COMMITTED visibility; "
            f"observed={isolation}"
        )
    cursor.execute(
        """
        UPDATE execution.document_persistence_run
        SET state_ref = 'publishing'
        WHERE stage_ref = %s AND state_ref = 'staged'
        """,
        (stage_ref,),
    )
    cursor.execute(
        "SELECT set_config('max_parallel_workers_per_gather', %s, true)",
        (str(runtime.worker_budget),),
    )
    return stage_ref


def _complete_stage(cursor: Any, *, stage_ref: str, statement_count: int) -> None:
    cursor.execute(
        "DELETE FROM execution.document_persistence_stage WHERE stage_ref = %s",
        (stage_ref,),
    )
    cursor.execute(
        """
        UPDATE execution.document_persistence_run
        SET state_ref = 'published', statement_count = %s,
            published_at = CURRENT_TIMESTAMP
        WHERE stage_ref = %s
        """,
        (statement_count, stage_ref),
    )


__all__ = [
    "WORK_CONSERVING_PERSISTENCE_CONTRACT",
    "DocumentPersistenceRuntime",
    "PersistenceRuntimeConfig",
    "StagePayload",
    "configure_work_conserving_persistence",
    "document_persistence_runtime",
]
