"""Activate work-conserving persistence for the canonical document compiler."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import pickle
from time import monotonic_ns
from types import MethodType
from typing import Any, Iterator

from src.policy.postgres_corpus_compilation import _operational_build_key
from src.storage.postgres.annotation_metadata_hot_path import (
    persist_annotation_layer_batches_single_pass,
)
from src.storage.postgres.pipelined_document_cursor import PipelinedDocumentCursor
from src.storage.postgres.work_conserving_persistence import (
    WORK_CONSERVING_PERSISTENCE_CONTRACT,
    activate_work_conserving_postgres_bindings,
    activate_work_conserving_store_bindings,
    document_persistence_runtime,
)
from src.storage.postgres.work_conserving_stage_hot_path import (
    summarize_document_persistence,
)


WORK_CONSERVING_DOCUMENT_EXECUTOR_REF = "document-executor:postgres-work-conserving:v0_1"


def _record_publication_transaction(runtime: Any, row: dict[str, int]) -> None:
    rows = getattr(runtime, "publication_transactions", None)
    if rows is None:
        rows = []
        setattr(runtime, "publication_transactions", rows)
    rows.append(row)


@contextmanager
def _claim_budget_at_document_savepoint(store: Any, runtime: Any) -> Iterator[None]:
    """Transfer the budget and pipeline the ordered publication transaction.

    The instrumentation here deliberately sits at the transaction boundary. It
    separates time spent executing the publication body from pipeline waits and
    from psycopg/PostgreSQL work performed while the savepoint context exits
    (commit, deferred constraints, WAL/fsync, etc.).
    """

    original_savepoint = store.savepoint

    @contextmanager
    def budgeted_savepoint() -> Iterator[Any]:
        runtime.ensure_budget()
        transaction_started = monotonic_ns()
        body_started = transaction_started
        body_finished = transaction_started
        pipeline_finished = transaction_started
        cursor_metrics: dict[str, int] = {}
        body_succeeded = False
        committed = False
        try:
            with original_savepoint() as cursor:
                body_started = monotonic_ns()
                pipelined = PipelinedDocumentCursor(cursor)
                try:
                    with pipelined:
                        yield pipelined
                    body_succeeded = True
                finally:
                    body_finished = monotonic_ns()
                    cursor_metrics = pipelined.publication_metrics
                pipeline_finished = monotonic_ns()
            committed = body_succeeded
        finally:
            transaction_finished = monotonic_ns()
            _record_publication_transaction(
                runtime,
                {
                    "body_succeeded": int(body_succeeded),
                    "committed": int(committed),
                    "transaction_total_ns": transaction_finished - transaction_started,
                    "body_ns": max(0, body_finished - body_started),
                    "pipeline_close_ns": max(0, pipeline_finished - body_finished),
                    "transaction_exit_ns": max(0, transaction_finished - pipeline_finished),
                    **cursor_metrics,
                },
            )

    store.savepoint = budgeted_savepoint
    try:
        yield
    finally:
        store.savepoint = original_savepoint


def _write_persistence_metrics(metrics: dict[str, Any]) -> None:
    raw = os.environ.get("SENSIBLAW_PERSISTENCE_METRICS_PATH")
    if not raw:
        return
    path = Path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(pickle.dumps(metrics, protocol=5))
    temporary.replace(path)


def _canonical_document_persistence() -> Any:
    """Return the operational persistence authority beneath strict parser wrapping."""

    from src.policy import postgres_corpus_compilation as postgres

    return getattr(
        postgres,
        "_persist_document_compilation_without_streaming_spacy",
        postgres.persist_document_compilation,
    )


def _publication_summary(runtime: Any) -> dict[str, Any]:
    rows = tuple(getattr(runtime, "publication_transactions", ()) or ())
    summed = {
        key: sum(int(row.get(key, 0)) for row in rows)
        for key in (
            "transaction_total_ns",
            "body_ns",
            "pipeline_close_ns",
            "transaction_exit_ns",
            "statement_count",
            "executemany_count",
            "execute_ns",
            "pipeline_sync_count",
            "pipeline_sync_ns",
            "copy_boundary_count",
            "copy_boundary_ns",
            "fetch_count",
        )
    }
    summed["transaction_count"] = len(rows)
    summed["body_success_count"] = sum(
        int(row.get("body_succeeded", 0)) for row in rows
    )
    summed["committed_transaction_count"] = sum(
        int(row.get("committed", 0)) for row in rows
    )
    summed["transactions"] = list(rows)
    return summed


def _superbatch_summary(runtime: Any) -> dict[str, int]:
    return {
        "graph_flushes": int(getattr(runtime, "graph_superbatches_flushed", 0)),
        "graph_payloads": int(getattr(runtime, "graph_superbatch_payloads", 0)),
        "resolution_flushes": int(getattr(runtime, "resolution_superbatches_flushed", 0)),
        "resolution_payloads": int(getattr(runtime, "resolution_superbatch_payloads", 0)),
        "binding_flushes": int(getattr(runtime, "binding_superbatches_flushed", 0)),
        "binding_payloads": int(getattr(runtime, "binding_superbatch_payloads", 0)),
        "verified_candidate_link_rows_cached": int(
            getattr(runtime, "verified_candidate_link_rows_cached", 0)
        ),
    }


def persist_document_compilation_work_conserving(**kwargs: Any) -> tuple[str, ...]:
    """Run the existing compiler with a parallel staged persistence substrate."""

    entry = kwargs["entry"]
    context = kwargs["context"]
    store = kwargs["store"]
    document_ref = str(entry["document_ref"])
    build_key_sha256 = _operational_build_key(
        document_ref=document_ref,
        content_sha256=str(entry["content_sha256"]),
        canonical_text_sha256=str(entry["canonical_text_sha256"]),
        media_adapter_ref=str(entry["media_adapter_ref"]),
        context=context,
        parser_workers=int(kwargs.get("parser_workers", 2)),
        parser_limit_chars=int(kwargs.get("parser_limit_chars", 1_000_000)),
        parser_target_chars=int(kwargs.get("parser_target_chars", 400_000)),
        parser_overlap_chars=int(kwargs.get("parser_overlap_chars", 8_192)),
    )
    runtime: Any
    executor_started = monotonic_ns()
    with document_persistence_runtime(
        document_ref=document_ref,
        build_key_sha256=build_key_sha256,
    ) as runtime:
        with _claim_budget_at_document_savepoint(store, runtime):
            with activate_work_conserving_store_bindings(store):
                original_annotation_batches = store.persist_annotation_layer_batches
                store.persist_annotation_layer_batches = MethodType(
                    persist_annotation_layer_batches_single_pass,
                    store,
                )
                try:
                    with activate_work_conserving_postgres_bindings():
                        result = _canonical_document_persistence()(**kwargs)
                finally:
                    store.persist_annotation_layer_batches = original_annotation_batches
    executor_wall_ns = monotonic_ns() - executor_started
    metrics = {
        "contract_ref": WORK_CONSERVING_PERSISTENCE_CONTRACT,
        "document_ref": document_ref,
        "build_key_sha256": build_key_sha256,
        "executor_wall_ns": executor_wall_ns,
        "publication": _publication_summary(runtime),
        "superbatches": _superbatch_summary(runtime),
        **summarize_document_persistence(runtime),
    }
    _write_persistence_metrics(metrics)
    resource_ledger = kwargs.get("resource_ledger")
    if resource_ledger is not None:
        resource_ledger.sample(
            "postgres_persistence:work_conserving_summary",
            phase="postgres_persistence",
            semantic_counts={
                "staged_rows": int(metrics.get("staged_rows") or 0),
                "stage_count": int(metrics.get("stage_count") or 0),
                "publication_transactions": int(
                    metrics["publication"].get("transaction_count") or 0
                ),
                "superbatch_flushes": sum(
                    int(value)
                    for key, value in metrics["superbatches"].items()
                    if key.endswith("_flushes")
                ),
            },
            details=metrics,
        )
    return result


__all__ = [
    "WORK_CONSERVING_DOCUMENT_EXECUTOR_REF",
    "WORK_CONSERVING_PERSISTENCE_CONTRACT",
    "persist_document_compilation_work_conserving",
]
