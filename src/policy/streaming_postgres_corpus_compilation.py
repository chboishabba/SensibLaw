"""Transactional PostgreSQL persistence for streaming semantic document builds."""

from __future__ import annotations

from time import monotonic_ns
from typing import Any, Mapping

from src.policy.corpus_compilation import CompilerContext
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    compile_document_operational,
)
from src.policy.postgres_corpus_compilation import (
    _canonical_source_coordinates,
    _operational_build_key,
    _operational_document_ref,
    _prepare_meets_for_relational_persistence,
    _validated_canonical_tokens,
)
from src.runtime.stage_timing import StageTiming
from src.storage.postgres import PostgresCompilerStore
from src.storage.postgres.binding_candidate_store import (
    persist_binding_candidate_sets,
)
from src.storage.postgres.factor_revision_store import persist_factor_revision
from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
    persist_completed_operational_build,
)
from src.storage.postgres.semantic_fibre_store import (
    persist_semantic_fibre_artifacts,
)
from src.storage.postgres.semantic_store import (
    persist_pnf_graph,
    persist_resolution_artifacts,
)
from src.storage.postgres.span_store import persist_licensed_spans
from src.storage.postgres.streaming_semantic_store import (
    persist_streaming_semantic_artifacts,
)


def _with_persistence_timing(
    ledger: Mapping[str, Any],
    *,
    document_ref: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    result = dict(ledger)
    timings = [dict(row) for row in ledger.get("timings") or ()]
    timing = StageTiming(
        document_ref=document_ref,
        stage="postgres_persistence",
        ordinal=len(timings),
        elapsed_ms=elapsed_ms,
        backend_ref="postgresql",
        details={
            "transaction_scope": "document_immutable_build",
            "excludes": [
                "semantic_stage_timing_insert",
                "completed_build_receipt_insert",
            ],
        },
    ).to_dict()
    timings.append(timing)
    totals = {
        str(key): int(value)
        for key, value in (ledger.get("stage_totals_ms") or {}).items()
    }
    totals["postgres_persistence"] = (
        totals.get("postgres_persistence", 0) + elapsed_ms
    )
    result["timings"] = timings
    result["stage_totals_ms"] = {
        key: totals[key] for key in sorted(totals)
    }
    return result


def persist_streaming_document_compilation(
    *,
    store: PostgresCompilerStore,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    source_text: str,
    context: CompilerContext,
    closure_workers: int = 2,
    owner_partitions: int = 2,
) -> tuple[str, ...]:
    """Compile and persist one immutable document and its fixed-point evidence."""

    document_ref = str(entry["document_ref"])
    content_sha256 = str(entry["content_sha256"])
    source_ref = f"document-source:{document_ref}"
    canonical_text, canonical_text_sha256, media_adapter_ref = (
        _canonical_source_coordinates(
            media_type=str(entry["media_type"]),
            source_text=source_text,
            source_ref=source_ref,
        )
    )
    expected_document_ref = _operational_document_ref(
        source_content_sha256=content_sha256,
        canonical_text_sha256=canonical_text_sha256,
        media_type=str(entry["media_type"]),
        media_adapter_ref=media_adapter_ref,
        context=context,
    )
    if document_ref != expected_document_ref:
        raise ValueError(
            "operational document identity disagrees with canonical text"
        )
    if str(entry.get("canonical_text_sha256") or "") != canonical_text_sha256:
        raise ValueError("manifest canonical text hash disagrees with compilation")
    if str(entry.get("media_adapter_ref") or "") != media_adapter_ref:
        raise ValueError("manifest media adapter disagrees with compilation")
    if str(entry.get("adapter_capability_ref") or "") != media_adapter_ref:
        raise ValueError(
            "declared media capability disagrees with selected adapter"
        )

    build_key_sha256 = _operational_build_key(
        document_ref=document_ref,
        content_sha256=content_sha256,
        canonical_text_sha256=canonical_text_sha256,
        media_adapter_ref=media_adapter_ref,
        context=context,
    )
    with store.transaction() as cursor:
        cached_demand_refs = load_completed_operational_build(
            cursor,
            document_ref=document_ref,
            compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
        )
        if cached_demand_refs is not None:
            store.persist_occurrence(
                cursor,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                document_ref=document_ref,
                state="reused_compilation",
            )
            return cached_demand_refs

    compilation = compile_document_operational(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "media_type": entry["media_type"],
            "canonical_text": source_text,
            "source_ref": source_ref,
        },
        context,
        closure_workers=closure_workers,
        owner_partitions=owner_partitions,
    )
    artifacts = compilation.artifacts
    if str(artifacts.get("build_key_sha256") or "") != build_key_sha256:
        raise ValueError(
            "operational compiler build key disagrees with persistence"
        )
    source_normalisation = artifacts.get("source_normalisation") or {}
    if str(source_normalisation.get("adapter_ref") or "") != media_adapter_ref:
        raise ValueError(
            "operational compiler media adapter disagrees with persistence"
        )
    canonical_tokens = _validated_canonical_tokens(
        artifacts=artifacts,
        expected_text=canonical_text,
        expected_sha256=canonical_text_sha256,
    )
    refinements = tuple(artifacts.get("factor_refinements") or ())
    candidate_sets = tuple(
        artifacts.get("binding_candidate_sets") or ()
    )
    factor_anchors = tuple(artifacts.get("factor_anchors") or ())
    candidate_set_builds = tuple(
        artifacts.get("binding_candidate_set_builds") or ()
    )
    demands = tuple(artifacts.get("resolution_demands") or ())
    meets = _prepare_meets_for_relational_persistence(
        artifacts.get("typed_meets") or ()
    )
    streaming_build = artifacts.get("streaming_semantic_build") or {}
    stage_timing = artifacts.get("semantic_stage_timing") or {}
    certificate = streaming_build.get("fixed_point_certificate") or {}
    if certificate.get("local_fixed_point") != "reached":
        raise ValueError(
            "only locally fixed-point streaming builds may be persisted"
        )

    persistence_started = monotonic_ns()
    with store.savepoint() as cursor:
        store.persist_source_document(
            cursor,
            document_ref=compilation.document_ref,
            media_type=compilation.media_type,
            content_sha256=compilation.content_sha256,
            source_bytes=source_bytes,
            canonical_text=canonical_text,
            adapter_ref=media_adapter_ref,
            adapter_version=context.media_normalization_ref,
            compiler_context_ref=context.context_ref,
            normalization_ref=context.media_normalization_ref,
        )
        store.persist_occurrence(
            cursor,
            corpus_ref=corpus_ref,
            relative_path=relative_path,
            document_ref=compilation.document_ref,
            state="compiled",
        )
        persist_licensed_spans(
            cursor,
            document_ref=compilation.document_ref,
            mentions=artifacts["licensing"].get("mentions") or (),
        )
        store.persist_tokens(
            cursor,
            document_ref=compilation.document_ref,
            tokenizer_ref=context.annotation_backend_ref,
            tokenizer_version=context.compiler_version,
            tokens=canonical_tokens,
        )
        store.persist_annotation_layer(
            cursor,
            document_ref=compilation.document_ref,
            layer=artifacts["annotation_layer"],
        )
        base_factor_revisions = persist_pnf_graph(
            cursor,
            document_ref=compilation.document_ref,
            graph=artifacts["pnf_graph"],
        )
        resulting_factor_revisions = dict(base_factor_revisions)
        for refinement in refinements:
            resulting = refinement.get("resulting_factor")
            if isinstance(resulting, Mapping):
                revision_ref = persist_factor_revision(
                    cursor,
                    document_ref=compilation.document_ref,
                    factor=resulting,
                )
                resulting_factor_revisions[
                    str(resulting["factor_ref"])
                ] = revision_ref
        demand_refs = persist_resolution_artifacts(
            cursor,
            factor_revisions=resulting_factor_revisions,
            demands=demands,
            evidence=artifacts.get("local_evidence") or (),
            meets=meets,
            refinements=refinements,
        )
        persist_binding_candidate_sets(
            cursor,
            candidate_sets=candidate_sets,
            refinements=refinements,
            factor_revisions=base_factor_revisions,
            factor_anchors=factor_anchors,
            builds=candidate_set_builds,
            meets=meets,
            demands=demands,
            validate_indexed_query=True,
        )
        elapsed_ms = max(
            0,
            (monotonic_ns() - persistence_started) // 1_000_000,
        )
        persisted_stage_timing = _with_persistence_timing(
            stage_timing,
            document_ref=compilation.document_ref,
            elapsed_ms=elapsed_ms,
        )
        persist_streaming_semantic_artifacts(
            cursor,
            document_ref=compilation.document_ref,
            streaming_build=streaming_build,
            stage_timing_ledger=persisted_stage_timing,
        )
        persist_semantic_fibre_artifacts(
            cursor,
            document_ref=compilation.document_ref,
            observation_deltas=tuple(
                row
                for row in streaming_build.get("observation_deltas") or ()
                if isinstance(row, Mapping)
            ),
            proposals=tuple(
                row
                for row in streaming_build.get("proposals") or ()
                if isinstance(row, Mapping)
            ),
            solver_jobs=tuple(
                row
                for row in streaming_build.get("solver_jobs") or ()
                if isinstance(row, Mapping)
            ),
            solver_receipts=tuple(
                row
                for row in streaming_build.get("solver_receipts") or ()
                if isinstance(row, Mapping)
            ),
            materialized_reduction=(
                streaming_build.get("materialized_reduction") or {}
            ),
            transports=tuple(
                row
                for row in streaming_build.get("semantic_transports") or ()
                if isinstance(row, Mapping)
            ),
            ontology_axes=tuple(
                row
                for row in streaming_build.get("ontology_axes") or ()
                if isinstance(row, Mapping)
            ),
            axis_obligations=tuple(
                row
                for row in streaming_build.get("axis_obligations") or ()
                if isinstance(row, Mapping)
            ),
            boundary_obligations=tuple(
                row
                for row in streaming_build.get("fibre_boundary_obligations") or ()
                if isinstance(row, Mapping)
            ),
        )
        persist_completed_operational_build(
            cursor,
            document_ref=compilation.document_ref,
            compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
            graph_ref=str(artifacts["pnf_graph"]["graph_ref"]),
            demand_refs=demand_refs,
        )
        return demand_refs


__all__ = ["persist_streaming_document_compilation"]
