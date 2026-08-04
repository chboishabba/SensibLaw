"""Install document-scoped execution strategies on the corpus compiler authority.

This module does not define another compiler. It replaces only execution-policy
callables on ``src.policy.corpus_compilation`` while retaining that module's
semantic types, globals, contracts and import identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import os
from threading import Lock
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence

from src.policy import document_graph_mentions as mention_execution
from src.policy.document_graph_mention_worker import scan_mention_partition
from src.policy.document_graph_projection import (
    DOCUMENT_GRAPH_PROJECTION_CONTRACT,
    collect_document_relational_bundle,
)


DOCUMENT_GRAPH_EXECUTION_CONTRACT = "document-graph-execution-strategy:v0_1"


@dataclass(frozen=True, slots=True)
class DocumentExecutionStrategy:
    """Execution-only declarations injected into the compiler authority."""

    contract_ref: str = DOCUMENT_GRAPH_EXECUTION_CONTRACT
    partitions_per_worker: int = 2
    min_parallel_tokens: int = 2_048
    min_parallel_sentences_per_worker: int = 1
    semantic_effect: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "mention_contract_ref": mention_execution.DOCUMENT_GRAPH_MENTION_CONTRACT,
            "projection_contract_ref": DOCUMENT_GRAPH_PROJECTION_CONTRACT,
            "semantic_object": "document_graph",
            "physical_partition": "operator_specific_fibre",
            "worker_budget_scope": "active_document",
            "mention_execution": "process_token_fibres",
            "projection_execution": "process_sentence_fibres",
            "merge": "deterministic_keyed_document_merge",
            "stage_semantic_authority": False,
            "fibre_semantic_authority": False,
            "commit_boundary": "single_document_transaction",
            "semantic_effect": self.semantic_effect,
        }


DEFAULT_DOCUMENT_EXECUTION_STRATEGY = DocumentExecutionStrategy()
_INSTALL_LOCK = Lock()
_PROJECTION_OVERRIDE_LOCK = Lock()


def _document_worker_budget(parsed_document: Mapping[str, Any] | None) -> int:
    override = os.getenv("SENSIBLAW_DOCUMENT_WORKERS", "").strip()
    if override:
        try:
            return max(1, min(32, int(override)))
        except ValueError:
            pass
    receipt = (parsed_document or {}).get("parser_receipt") or {}
    if isinstance(receipt, Mapping):
        raw = receipt.get("worker_count") or receipt.get("granted_workers") or 1
        try:
            return max(1, min(32, int(raw)))
        except (TypeError, ValueError):
            pass
    return 1


def _execution_measures(receipt: Mapping[str, Any]) -> dict[str, int]:
    return {
        "partitions_completed": int(receipt.get("partition_count") or 0),
        "worker_leases_granted": int(receipt.get("granted_workers") or 0),
        "worker_processes_observed": len(receipt.get("worker_pids") or ()),
        "worker_compute_ms": int(receipt.get("worker_compute_ms") or 0),
        "owner_merge_ms": int(receipt.get("owner_merge_ms") or 0),
    }


def install_document_execution_strategy(
    compiler: ModuleType,
    *,
    strategy: DocumentExecutionStrategy = DEFAULT_DOCUMENT_EXECUTION_STRATEGY,
) -> ModuleType:
    """Inject execution policy into the existing corpus compiler module.

    Installation is idempotent. Original semantic callables are retained on
    private attributes for parity checks, tests and exact serial fallbacks.
    """

    with _INSTALL_LOCK:
        installed = getattr(compiler, "_document_execution_strategy", None)
        if installed is not None:
            return compiler

        mention_execution._mention_worker = scan_mention_partition
        serial_mention_builder = compiler.build_mention_licensing_carrier
        serial_semantic_layer = compiler._semantic_annotation_layer
        compiler._serial_build_mention_licensing_carrier = serial_mention_builder
        compiler._serial_semantic_annotation_layer = serial_semantic_layer

        def build_mention_licensing_carrier(
            *,
            canonical_text: str,
            source_ref: str,
            document_ref: str,
            context_refs: Sequence[str] = (),
            parsed_document: Mapping[str, Any] | None = None,
            tokens: Sequence[tuple[str, int, int]] | None = None,
            progress_observer: Callable[[Mapping[str, Any]], None] | None = None,
        ) -> dict[str, Any]:
            worker_budget = _document_worker_budget(parsed_document)
            if worker_budget <= 1 or (
                tokens is not None and len(tokens) < strategy.min_parallel_tokens
            ):
                return serial_mention_builder(
                    canonical_text=canonical_text,
                    source_ref=source_ref,
                    document_ref=document_ref,
                    context_refs=context_refs,
                    parsed_document=parsed_document,
                    tokens=tokens,
                    progress_observer=progress_observer,
                )
            carrier = mention_execution.build_document_mention_licensing_carrier(
                canonical_text=canonical_text,
                source_ref=source_ref,
                document_ref=document_ref,
                context_refs=context_refs,
                parsed_document=parsed_document,
                tokens=tokens,
                progress_observer=progress_observer,
                worker_budget=worker_budget,
                partitions_per_worker=strategy.partitions_per_worker,
                min_parallel_tokens=strategy.min_parallel_tokens,
                verify_serial=False,
            )
            receipt = carrier.get("licensing_execution_receipt") or {}
            if progress_observer is not None and isinstance(receipt, Mapping):
                progress_observer(_execution_measures(receipt))
            return carrier

        def semantic_annotation_layer(
            *,
            document_ref: str,
            source_ref: str,
            content_sha256: str,
            tokens: Sequence[tuple[str, int, int]],
            base_layer: Any,
            text: str,
            parsed_document: Mapping[str, Any],
            progress_observer: Callable[[Mapping[str, int]], None] | None = None,
        ):
            worker_budget = _document_worker_budget(parsed_document)
            min_parallel_sentences = max(
                4,
                worker_budget * strategy.min_parallel_sentences_per_worker,
            )
            if worker_budget <= 1 or len(
                parsed_document.get("sents") or ()
            ) < min_parallel_sentences:
                return serial_semantic_layer(
                    document_ref=document_ref,
                    source_ref=source_ref,
                    content_sha256=content_sha256,
                    tokens=tokens,
                    base_layer=base_layer,
                    text=text,
                    parsed_document=parsed_document,
                    progress_observer=progress_observer,
                )
            parallel_collector = partial(
                collect_document_relational_bundle,
                worker_budget=worker_budget,
                partitions_per_worker=strategy.partitions_per_worker,
                min_parallel_sentences=min_parallel_sentences,
                verify_serial=False,
            )
            # The stable semantic-layer implementation currently resolves its
            # reducer through a module global. Guard the temporary execution
            # substitution under the one-active-document tranche invariant.
            with _PROJECTION_OVERRIDE_LOCK:
                previous = compiler.collect_canonical_relational_bundle
                compiler.collect_canonical_relational_bundle = parallel_collector
                try:
                    result = serial_semantic_layer(
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
                    compiler.collect_canonical_relational_bundle = previous
            _semantic_layer, relational_bundle, _atom_span_refs = result
            receipt = relational_bundle.get("projection_receipt") or {}
            if progress_observer is not None and isinstance(receipt, Mapping):
                progress_observer(_execution_measures(receipt))
            return result

        build_mention_licensing_carrier.__name__ = serial_mention_builder.__name__
        build_mention_licensing_carrier.__qualname__ = (
            serial_mention_builder.__qualname__
        )
        build_mention_licensing_carrier.__module__ = compiler.__name__
        semantic_annotation_layer.__name__ = serial_semantic_layer.__name__
        semantic_annotation_layer.__qualname__ = serial_semantic_layer.__qualname__
        semantic_annotation_layer.__module__ = compiler.__name__

        compiler.build_mention_licensing_carrier = build_mention_licensing_carrier
        compiler._semantic_annotation_layer = semantic_annotation_layer
        compiler.DOCUMENT_GRAPH_EXECUTION_CONTRACT = DOCUMENT_GRAPH_EXECUTION_CONTRACT
        compiler.DOCUMENT_GRAPH_MENTION_CONTRACT = (
            mention_execution.DOCUMENT_GRAPH_MENTION_CONTRACT
        )
        compiler.DOCUMENT_GRAPH_PROJECTION_CONTRACT = (
            DOCUMENT_GRAPH_PROJECTION_CONTRACT
        )
        compiler.document_execution_strategy = strategy
        compiler.document_execution_strategy_receipt = strategy.to_dict
        compiler._document_execution_strategy = strategy
        return compiler


__all__ = [
    "DEFAULT_DOCUMENT_EXECUTION_STRATEGY",
    "DOCUMENT_GRAPH_EXECUTION_CONTRACT",
    "DocumentExecutionStrategy",
    "install_document_execution_strategy",
]
