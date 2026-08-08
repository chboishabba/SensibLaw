"""Activate work-conserving persistence for the canonical document compiler."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from src.policy.postgres_corpus_compilation import (
    _operational_build_key,
    persist_document_compilation,
)
from src.storage.postgres.work_conserving_persistence import (
    WORK_CONSERVING_PERSISTENCE_CONTRACT,
    activate_work_conserving_postgres_bindings,
    activate_work_conserving_store_bindings,
    document_persistence_runtime,
)


WORK_CONSERVING_DOCUMENT_EXECUTOR_REF = (
    "document-executor:postgres-work-conserving:v0_1"
)


@contextmanager
def _claim_budget_at_document_savepoint(
    store: Any, runtime: Any
) -> Iterator[None]:
    """Transfer the full budget at the exact persistence boundary."""

    original_savepoint = store.savepoint

    @contextmanager
    def budgeted_savepoint() -> Iterator[Any]:
        runtime.ensure_budget()
        with original_savepoint() as cursor:
            yield cursor

    store.savepoint = budgeted_savepoint
    try:
        yield
    finally:
        store.savepoint = original_savepoint


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
    with document_persistence_runtime(
        document_ref=document_ref,
        build_key_sha256=build_key_sha256,
    ) as runtime:
        with _claim_budget_at_document_savepoint(store, runtime):
            with activate_work_conserving_store_bindings(store):
                with activate_work_conserving_postgres_bindings():
                    return persist_document_compilation(**kwargs)


__all__ = [
    "WORK_CONSERVING_DOCUMENT_EXECUTOR_REF",
    "WORK_CONSERVING_PERSISTENCE_CONTRACT",
    "persist_document_compilation_work_conserving",
]
