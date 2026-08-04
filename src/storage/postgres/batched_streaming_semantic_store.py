"""Bounded persistence dispatch for streaming semantic evidence.

Reference-backed exact-document builds are consumed in verified 256-row
batches.  Small embedded fixtures retain the established row-wise compatibility
store.  This module deliberately no longer constructs document-wide
``executemany`` parameter lists while claiming to be batched.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.storage.postgres.reference_streaming_semantic_store import (
    DEFAULT_BATCH_SIZE,
    persist_reference_streaming_semantic_artifacts,
)
from src.storage.postgres.streaming_semantic_store import (
    persist_streaming_semantic_artifacts,
)


def persist_streaming_semantic_artifacts_batched(
    cursor: Any,
    *,
    document_ref: str,
    streaming_build: Mapping[str, Any],
    stage_timing_ledger: Mapping[str, Any],
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    """Persist one build without document-wide client parameter arrays."""

    if streaming_build.get("reference_backed"):
        persist_reference_streaming_semantic_artifacts(
            cursor,
            document_ref=document_ref,
            streaming_build=streaming_build,
            stage_timing_ledger=stage_timing_ledger,
            batch_size=batch_size,
        )
        return
    persist_streaming_semantic_artifacts(
        cursor,
        document_ref=document_ref,
        streaming_build=streaming_build,
        stage_timing_ledger=stage_timing_ledger,
    )


__all__ = ["persist_streaming_semantic_artifacts_batched"]
