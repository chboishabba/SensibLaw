"""Activate work-conserving persistence for the canonical document compiler."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import pickle
from typing import Any, Iterator

from src.policy.postgres_corpus_compilation import (
    _operational_build_key,
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


WORK_CONSERVING_DOCUMENT_EXECUTOR_REF = (
    "document-executor:postgres-work-conserving:v0_1"
)


@contextmanager
def _claim_budget_at_document_savepoint(store: Any, runtime: Any) -> Iterator[None]:
    """Transfer the budget and pipeline the ordered publication transaction."""

    original_savepoint = store.savepoint

    @contextmanager
    def budgeted_savepoint() -> Iterator[Any]:
        runtime.ensure_budget()
        with original_savepoint() as cursor:
            with PipelinedDocumentCursor(cursor) as pipelined:
                yield pipelined

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


def persist_document_compilation_work_conserving(**kwargs: Any) -> tuple[str, ...]:
    """Run the existing compiler with a parallel staged persistence substrate.

    Semantic compilation, closure, parent validation, completed-build
    publication, and occurrence publication remain owned by
    ``persist_document_compilation``. Only physical persistence helpers and
    high-volume store methods are rebound for this one ordered document.
    """

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
    with document_persistence_runtime(
        document_ref=document_ref,
        build_key_sha256=build_key_sha256,
    ) as runtime:
        with _claim_budget_at_document_savepoint(store, runtime):
            with activate_work_conserving_store_bindings(store):
                with activate_work_conserving_postgres_bindings():
                    result = _canonical_document_persistence()(**kwargs)
    metrics = {
        "contract_ref": WORK_CONSERVING_PERSISTENCE_CONTRACT,
        "document_ref": document_ref,
        "build_key_sha256": build_key_sha256,
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
            },
            details=metrics,
        )
    return result


__all__ = [
    "WORK_CONSERVING_DOCUMENT_EXECUTOR_REF",
    "WORK_CONSERVING_PERSISTENCE_CONTRACT",
    "persist_document_compilation_work_conserving",
]
