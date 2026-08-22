"""Work-conserving, set-based PostgreSQL persistence beneath one document commit.

The semantic compiler and ordered world fold remain unchanged. High-volume rows
are copied into typed execution-only staging by multiple PostgreSQL backends,
then merged into authority tables by a fixed number of set operations inside
the caller's existing document savepoint. Staged rows never publish a document.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from src.policy.carrier_orchestration_hot_path import (
    activate_carrier_orchestration_hot_path,
)
from src.storage.postgres import (
    work_conserving_binding_persistence as binding_persistence,
)
from src.storage.postgres import work_conserving_graph_persistence as graph_persistence
from src.storage.postgres import (
    work_conserving_language_persistence as language_persistence,
)
from src.storage.postgres import (
    work_conserving_resolution_persistence as resolution_persistence,
)
from src.storage.postgres.manifest_metadata_hot_path import (
    install_descriptor_metadata_hot_path,
)
from src.storage.postgres.verified_candidate_link_cache import (
    install_verified_candidate_link_cache,
)
from src.storage.postgres.work_conserving_binding_batching import (
    flush_binding_batch,
    persist_binding_batched,
    persist_streamed_candidate_builds_batched,
    persist_streamed_candidate_links_batched,
)
from src.storage.postgres.work_conserving_binding_persistence import (
    _binding_payloads,
    persist_binding_candidate_sets_work_conserving,
)
from src.storage.postgres.work_conserving_copy_observability import (
    observable_complete_stage,
    observable_stage_partition,
    observable_stage_payloads,
)
from src.storage.postgres.work_conserving_graph_batching import (
    flush_graph_batch,
    persist_pnf_graph_batched,
)
from src.storage.postgres.work_conserving_graph_persistence import (
    _factor_payloads,
    deferred_factor_revision,
    persist_licensed_spans_work_conserving,
    persist_pnf_graph_work_conserving,
)
from src.storage.postgres.work_conserving_language_persistence import (
    activate_work_conserving_store_bindings,
    persist_annotation_layer_batches_work_conserving,
    persist_annotation_layer_work_conserving,
    persist_token_batches_work_conserving,
)
from src.storage.postgres.work_conserving_resolution_batching import (
    flush_resolution_batch,
    persist_resolution_batched,
)
from src.storage.postgres.work_conserving_resolution_persistence import (
    _resolution_payloads,
    persist_resolution_artifacts_work_conserving,
)
from src.storage.postgres.work_conserving_stage import (
    WORK_CONSERVING_PERSISTENCE_CONTRACT,
    DocumentPersistenceRuntime,
    PersistenceRuntimeConfig,
    StagePayload,
    _prepare_stage,
    configure_work_conserving_persistence,
    document_persistence_runtime,
)
from src.storage.postgres.work_conserving_stage_hot_path import (
    install_work_conserving_stage_hot_path,
)


@contextmanager
def activate_work_conserving_postgres_bindings() -> Iterator[None]:
    """Temporarily replace only physical persistence helpers in the compiler."""

    import src.policy.postgres_corpus_compilation as compiler
    from src.storage.postgres import work_conserving_stage as stage

    install_work_conserving_stage_hot_path()

    original_completed_build = compiler.persist_completed_operational_build
    original_descriptor_family = compiler._iter_descriptor_family
    original_descriptor_metadata = compiler._descriptor_metadata

    def persist_completed_build_after_flush(cursor: Any, **kwargs: Any) -> None:
        flush_binding_batch(cursor)
        flush_resolution_batch(cursor)
        flush_graph_batch(cursor)
        original_completed_build(cursor, **kwargs)

    replacements = {
        "persist_licensed_spans": persist_licensed_spans_work_conserving,
        "persist_pnf_graph": persist_pnf_graph_batched,
        "persist_factor_revision": deferred_factor_revision,
        "persist_resolution_artifacts": persist_resolution_batched,
        "persist_binding_candidate_sets": persist_binding_batched,
        "_persist_streamed_candidate_builds": persist_streamed_candidate_builds_batched,
        "_persist_streamed_candidate_links": persist_streamed_candidate_links_batched,
        "persist_completed_operational_build": persist_completed_build_after_flush,
    }
    helper_modules = (
        graph_persistence,
        language_persistence,
        resolution_persistence,
        binding_persistence,
    )
    compiler_originals = {name: getattr(compiler, name) for name in replacements}
    helper_originals = {
        module: (module._stage_payloads, module._complete_stage)
        for module in helper_modules
    }
    original_stage_partition = stage._stage_partition

    def flush_pending_batches() -> None:
        """Flush only when this binding scope owns a document runtime."""

        if stage._DOCUMENT_RUNTIME.get() is None:
            return
        flush_binding_batch()
        flush_resolution_batch()
        flush_graph_batch()

    for name, replacement in replacements.items():
        setattr(compiler, name, replacement)
    install_verified_candidate_link_cache(compiler)
    install_descriptor_metadata_hot_path(compiler)
    stage._stage_partition = observable_stage_partition
    for module in helper_modules:
        module._stage_payloads = observable_stage_payloads
        module._complete_stage = observable_complete_stage
    try:
        with activate_carrier_orchestration_hot_path():
            yield
            flush_pending_batches()
    finally:
        compiler._iter_descriptor_family = original_descriptor_family
        compiler._descriptor_metadata = original_descriptor_metadata
        for module, originals in helper_originals.items():
            module._stage_payloads, module._complete_stage = originals
        stage._stage_partition = original_stage_partition
        for name, original in compiler_originals.items():
            setattr(compiler, name, original)


__all__ = [
    "WORK_CONSERVING_PERSISTENCE_CONTRACT",
    "DocumentPersistenceRuntime",
    "PersistenceRuntimeConfig",
    "StagePayload",
    "_binding_payloads",
    "_factor_payloads",
    "_prepare_stage",
    "_resolution_payloads",
    "activate_work_conserving_postgres_bindings",
    "activate_work_conserving_store_bindings",
    "configure_work_conserving_persistence",
    "deferred_factor_revision",
    "document_persistence_runtime",
    "persist_annotation_layer_batches_work_conserving",
    "persist_annotation_layer_work_conserving",
    "persist_binding_candidate_sets_work_conserving",
    "persist_pnf_graph_work_conserving",
    "persist_resolution_artifacts_work_conserving",
    "persist_token_batches_work_conserving",
]
