"""Live and failure-surviving progress for strict numeric PNF execution.

This module does not introduce a second semantic execution path.  It observes
existing durable PostgreSQL carriers and wraps the already-installed streaming
kernels only to announce start/completion/failure boundaries.

Two evidence classes are intentionally kept distinct:

* live snapshots: queue/cardinality state sampled from PostgreSQL;
* completed-kernel timings: monotonic intervals emitted around existing Python
  coordinator kernels plus PostgreSQL timing receipts already written by the
  sparse frontier reducer.

The summed per-interface frontier ``elapsed_ms`` values are work totals, not
wall-time intervals; callers must not add them to coordinator wall time as if
they were disjoint.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Event, Thread
from time import monotonic_ns, time_ns
from typing import Any, Callable, Iterator, Mapping

from src.storage.postgres.spacy_parser_model import connect


ProgressObserver = Callable[[Mapping[str, Any]], None]
_CURRENT_OBSERVER: ContextVar[ProgressObserver | None] = ContextVar(
    "sensiblaw_numeric_kernel_progress_observer", default=None
)
_INSTALL_MARKER = "_numeric_kernel_progress_instrumentation_installed"


def _emit(payload: Mapping[str, Any]) -> None:
    observer = _CURRENT_OBSERVER.get()
    if observer is not None:
        observer(dict(payload))


def _named_counts(rows: list[tuple[Any, ...]]) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in rows}


def numeric_kernel_progress_snapshot(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> dict[str, Any]:
    """Read compact progress/timing state without scanning semantic interiors."""

    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*),
                    count(*) FILTER (WHERE state = 'ready'),
                    count(*) FILTER (WHERE state = 'leased'),
                    count(*) FILTER (WHERE state = 'completed'),
                    count(*) FILTER (WHERE state = 'failed'),
                    COALESCE(sum(token_count) FILTER (WHERE state = 'completed'), 0),
                    COALESCE(sum(elapsed_ns) FILTER (WHERE state = 'completed'), 0)
                  FROM execution.semantic_parser_partition
                 WHERE run_ref = %s AND document_ref = %s
                """,
                (run_ref, document_ref),
            )
            parser_row = cursor.fetchone() or (0, 0, 0, 0, 0, 0, 0)

            cursor.execute(
                """
                SELECT operation_id || ':' || state_id, count(*)
                  FROM execution.semantic_pnf_work_item
                 WHERE run_ref = %s AND document_ref = %s
                 GROUP BY operation_id, state_id
                 ORDER BY operation_id, state_id
                """,
                (run_ref, document_ref),
            )
            work_counts = _named_counts(cursor.fetchall())

            cursor.execute(
                """
                SELECT region_kind,
                       count(*),
                       count(*) FILTER (WHERE closure_state IN (2, 3)),
                       count(*) FILTER (WHERE closure_state = 3)
                  FROM execution.semantic_pnf_region
                 WHERE run_ref = %s AND document_ref = %s
                 GROUP BY region_kind
                 ORDER BY region_kind
                """,
                (run_ref, document_ref),
            )
            region_counts = {
                str(int(kind)): {
                    "total": int(total),
                    "locally_or_fully_closed": int(locally_closed),
                    "fully_closed": int(closed),
                }
                for kind, total, locally_closed, closed in cursor.fetchall()
            }

            cursor.execute(
                """
                SELECT region.region_kind,
                       count(*),
                       COALESCE(sum(receipt.elapsed_ms), 0),
                       COALESCE(sum(receipt.input_export_count), 0),
                       COALESCE(sum(receipt.output_export_count), 0)
                  FROM execution.semantic_pnf_frontier_reduction_receipt AS receipt
                  JOIN execution.semantic_pnf_interface AS interface
                    ON interface.interface_id = receipt.interface_id
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id = interface.region_id
                 WHERE region.run_ref = %s
                   AND region.document_ref = %s
                 GROUP BY region.region_kind
                 ORDER BY region.region_kind
                """,
                (run_ref, document_ref),
            )
            frontier_by_kind = {
                str(int(kind)): {
                    "receipt_count": int(receipt_count),
                    "summed_interface_elapsed_ms": float(elapsed_ms),
                    "input_export_count": int(input_exports),
                    "output_export_count": int(output_exports),
                }
                for (
                    kind,
                    receipt_count,
                    elapsed_ms,
                    input_exports,
                    output_exports,
                ) in cursor.fetchall()
            }

            cursor.execute(
                """
                SELECT DISTINCT region.run_id, region.document_id
                  FROM execution.semantic_pnf_region AS region
                 WHERE region.run_ref = %s
                   AND region.document_ref = %s
                 LIMIT 1
                """,
                (run_ref, document_ref),
            )
            numeric_scope = cursor.fetchone()
            frontier_stages: dict[str, dict[str, int | float]] = {}
            if numeric_scope is not None:
                cursor.execute(
                    """
                    SELECT stage_name, row_count, elapsed_ms
                      FROM execution.semantic_pnf_frontier_stage_receipt
                     WHERE run_id = %s AND document_id = %s
                     ORDER BY stage_name
                    """,
                    (int(numeric_scope[0]), int(numeric_scope[1])),
                )
                frontier_stages = {
                    str(stage_name): {
                        "row_count": int(row_count),
                        "elapsed_ms": float(elapsed_ms),
                    }
                    for stage_name, row_count, elapsed_ms in cursor.fetchall()
                }
    finally:
        connection.close()

    return {
        "schema_version": "sensiblaw.numeric-kernel-progress.v1",
        "observed_epoch_ns": time_ns(),
        "run_ref": run_ref,
        "document_ref": document_ref,
        "parser": {
            "partition_total": int(parser_row[0]),
            "partition_ready": int(parser_row[1]),
            "partition_leased": int(parser_row[2]),
            "partition_completed": int(parser_row[3]),
            "partition_failed": int(parser_row[4]),
            "completed_token_count": int(parser_row[5]),
            # This is the parser-active timing stored on completed partition
            # receipts, not projection/closure/coordinator wall time.
            "summed_parser_work_ns": int(parser_row[6]),
        },
        "pnf_work_operation_state_counts": work_counts,
        "region_closure_by_kind": region_counts,
        "frontier_reduction_by_kind": frontier_by_kind,
        "frontier_stage_receipts": frontier_stages,
        "timing_semantics": {
            "frontier_elapsed": "sum of completed interface reducer work receipts",
            "parser_elapsed": "sum of completed partition parser-active work",
            "snapshot": "observational; no semantic identity authority",
        },
    }


class NumericKernelProgressSampler:
    """Periodically publish compact PostgreSQL progress while a kernel blocks."""

    def __init__(
        self,
        *,
        database_url: str,
        run_ref: str,
        document_ref: str,
        observer: ProgressObserver | None,
        interval_seconds: float = 30.0,
    ) -> None:
        self.database_url = database_url
        self.run_ref = run_ref
        self.document_ref = document_ref
        self.observer = observer
        self.interval_seconds = max(1.0, float(interval_seconds))
        self._stop = Event()
        self._thread: Thread | None = None

    def _sample(self) -> None:
        if self.observer is None:
            return
        try:
            snapshot = numeric_kernel_progress_snapshot(
                self.database_url,
                run_ref=self.run_ref,
                document_ref=self.document_ref,
            )
        except BaseException as error:
            self.observer(
                {
                    "progress_probe_state": "failed",
                    "progress_probe_error_type": type(error).__name__,
                    "progress_probe_error": str(error),
                }
            )
            return
        self.observer(
            {
                "progress_probe_state": "observed",
                "numeric_kernel_snapshot": snapshot,
            }
        )

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def __enter__(self) -> "NumericKernelProgressSampler":
        self._sample()
        if self.observer is not None:
            self._thread = Thread(
                target=self._run,
                name=f"numeric-kernel-progress-{self.run_ref}",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds / 2))
        self._sample()


def _instrument_call(name: str, function: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = monotonic_ns()
        _emit(
            {
                "current_kernel": name,
                "kernel_state": "started",
            }
        )
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            _emit(
                {
                    "current_kernel": name,
                    "kernel_state": "failed",
                    "kernel_elapsed_ns": monotonic_ns() - started,
                    "kernel_error_type": type(error).__name__,
                    "kernel_error": str(error),
                }
            )
            raise
        _emit(
            {
                "current_kernel": name,
                "kernel_state": "completed",
                "kernel_elapsed_ns": monotonic_ns() - started,
            }
        )
        return result

    return wrapped


def install_numeric_streaming_kernel_instrumentation() -> bool:
    """Wrap current streaming coordinator kernels without replacing semantics."""

    from src.storage.postgres import streaming_spacy_execution as streaming

    if getattr(streaming, _INSTALL_MARKER, False):
        return False

    streaming._drain_remaining_sentence_closure = _instrument_call(
        "sentence_closure_coordinator",
        streaming._drain_remaining_sentence_closure,
    )

    original_adjacent = streaming._drain_remaining_adjacent_reconciliation

    @wraps(original_adjacent)
    def adjacent(*args: Any, **kwargs: Any) -> Any:
        stage = str(kwargs.get("stage") or "unknown")
        return _instrument_call(
            f"{stage}_adjacency",
            original_adjacent,
        )(*args, **kwargs)

    streaming._drain_remaining_adjacent_reconciliation = adjacent
    streaming.materialize_numeric_document_hierarchy = _instrument_call(
        "numeric_hierarchy",
        streaming.materialize_numeric_document_hierarchy,
    )
    streaming._refresh_final_numeric_lookup = _instrument_call(
        "root_lookup_publication",
        streaming._refresh_final_numeric_lookup,
    )
    streaming.numeric_execution_summary = _instrument_call(
        "numeric_execution_summary",
        streaming.numeric_execution_summary,
    )
    setattr(streaming, _INSTALL_MARKER, True)
    return True


@contextmanager
def numeric_streaming_kernel_progress(
    observer: ProgressObserver | None,
) -> Iterator[None]:
    """Bind one document's observer to already-installed coordinator wrappers."""

    install_numeric_streaming_kernel_instrumentation()
    token = _CURRENT_OBSERVER.set(observer)
    try:
        yield
    finally:
        _CURRENT_OBSERVER.reset(token)


__all__ = [
    "NumericKernelProgressSampler",
    "install_numeric_streaming_kernel_instrumentation",
    "numeric_kernel_progress_snapshot",
    "numeric_streaming_kernel_progress",
]
