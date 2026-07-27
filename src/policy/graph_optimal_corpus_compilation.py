"""Compatibility bridge from the staged compiler to document-graph execution.

The stable corpus compiler remains the source of data classes, carrier contracts
and ordinary compiler functions.  ``src.policy`` installs an import-order-stable
module proxy that forwards those attributes and monkeypatches to the stable
module while selecting the graph-enabled semantic projection below.

The override is guarded because the legacy semantic-layer function resolves its
collector through a module global.  The tranche objective is intentionally one
active document at a time, so this bridge preserves that execution invariant
until the semantic-layer dependency is made explicit in a later refactor.
"""

from __future__ import annotations

from functools import partial
import importlib
import os
from threading import Lock
from typing import Any, Mapping, Sequence

from src.policy.document_graph_projection import (
    DOCUMENT_GRAPH_PROJECTION_CONTRACT,
    collect_document_relational_bundle,
)


GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT = (
    "document-graph-corpus-compilation-bridge:v0_1"
)

_legacy = importlib.import_module("src.policy.corpus_compilation")
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_projection_override_lock = Lock()
_original_semantic_annotation_layer = _legacy._semantic_annotation_layer


def _document_worker_budget(parsed_document: Mapping[str, Any]) -> int:
    override = os.getenv("SENSIBLAW_DOCUMENT_WORKERS", "").strip()
    if override:
        try:
            return max(1, min(32, int(override)))
        except ValueError:
            pass
    receipt = parsed_document.get("parser_receipt") or {}
    if isinstance(receipt, Mapping):
        raw = receipt.get("worker_count") or receipt.get("granted_workers") or 1
        try:
            return max(1, min(32, int(raw)))
        except (TypeError, ValueError):
            pass
    return 1


def _semantic_annotation_layer(
    *,
    document_ref: str,
    source_ref: str,
    content_sha256: str,
    tokens: Sequence[tuple[str, int, int]],
    base_layer: Any,
    text: str,
    parsed_document: Mapping[str, Any],
    progress_observer=None,
):
    """Project parser observations with the active document's worker budget."""

    worker_budget = _document_worker_budget(parsed_document)
    parallel_collector = partial(
        collect_document_relational_bundle,
        worker_budget=worker_budget,
        partitions_per_worker=2,
        min_parallel_sentences=max(4, worker_budget),
        verify_serial=False,
    )
    with _projection_override_lock:
        previous = _legacy.collect_canonical_relational_bundle
        _legacy.collect_canonical_relational_bundle = parallel_collector
        try:
            return _original_semantic_annotation_layer(
                document_ref=document_ref,
                source_ref=source_ref,
                content_sha256=content_sha256,
                tokens=tokens,
                base_layer=base_layer,
                text=text,
                parsed_document=parsed_document,
                progress_observer=progress_observer,
            )
        finally:
            _legacy.collect_canonical_relational_bundle = previous


def graph_execution_contract() -> dict[str, Any]:
    return {
        "contract_ref": GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT,
        "projection_contract_ref": DOCUMENT_GRAPH_PROJECTION_CONTRACT,
        "semantic_object": "document_graph",
        "physical_partition": "operator_specific_fibre",
        "worker_budget_scope": "active_document",
        "projection_execution": "process_sentence_fibres",
        "merge": "deterministic_keyed_document_merge",
        "stage_semantic_authority": False,
        "fibre_semantic_authority": False,
        "commit_boundary": "single_document_transaction",
    }


__all__ = sorted(
    {
        *(name for name in dir(_legacy) if not name.startswith("__")),
        "DOCUMENT_GRAPH_PROJECTION_CONTRACT",
        "GRAPH_OPTIMAL_CORPUS_COMPILATION_CONTRACT",
        "graph_execution_contract",
    }
)
