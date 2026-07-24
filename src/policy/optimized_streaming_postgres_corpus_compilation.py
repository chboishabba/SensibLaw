"""Timed, batched PostgreSQL persistence for one immutable fibred document.

This module preserves semantic identities while changing execution: canonical
parent-before-child batching, nested persistence timings, and one document
transaction suitable for whole-attempt retry by the caller.
"""

from __future__ import annotations

from time import monotonic_ns
from typing import Any, Mapping

from src.policy.corpus_compilation import CompilerContext
from src.policy.fibred_operational_corpus_compilation import (
    FIBRED_OPERATIONAL_COMPILER_CONTRACT,
    compile_document_fibred_operational,
)
from src.policy.postgres_corpus_compilation import (
    _canonical_source_coordinates,
    _operational_build_key,
    _operational_document_ref,
    _prepare_meets_for_relational_persistence,
    _validated_canonical_tokens,
)
from src.runtime.stage_timing import StageTiming
from src.storage.postgres.batched_compiler_store import BatchedPostgresCompilerStore
from src.storage.postgres.batched_semantic_fibre_store import (
    persist_semantic_fibre_artifacts_batched,
)
from src.storage.postgres.batched_semantic_store import (
    persist_pnf_graph_batched,
    persist_resolution_artifacts_batched,
)
from src.storage.postgres.batched_streaming_semantic_store import (
    persist_streaming_semantic_artifacts_batched,
)
from src.storage.postgres.binding_candidate_store import (
    persist_binding_candidate_sets,
)
from src.storage.postgres.factor_revision_store import persist_factor_revision
from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
    persist_completed_operational_build,
)
from src.storage.postgres.proposal_parent_store import (
    persist_factor_proposal_parents,
)
from src.storage.postgres.semantic_lifecycle_store import (
    persist_semantic_lifecycle_artifacts,
)
from src.storage.postgres.span_store import persist_licensed_spans
from src.storage.postgres.stage_timing_store import persist_stage_timings


def _elapsed_ms(started_ns: int) -> int:
    return max(0, (monotonic_ns() - started_ns) // 1_000_000)


def _append_timing(
    ledger: dict[str, Any],
    *,
    document_ref: str,
    stage: str,
    elapsed_ms: int,
    details: Mapping[str, Any],
    input_nodes: int | None = None,
    output_nodes: int | None = None,
) -> dict[str, Any]:
    timings = [dict(row) for row in ledger.get("timings") or ()]
    row = StageTiming(
        document_ref=document_ref,
        stage=stage,
        ordinal=len(timings),
        elapsed_ms=elapsed_ms,
        backend_ref="postgresql",
        input_nodes=input_nodes,
        output_nodes=output_nodes,
        details=dict(details),
    ).to_dict()
    timings.append(row)
    totals = {
        str(key): int(value)
        for key, value in (ledger.get("stage_totals_ms") or {}).items()
    }
    totals[stage] = totals.get(stage, 0) + elapsed_ms
    return {
        **ledger,
        "timings": timings,
        "stage_totals_ms": {key: totals[key] for key in sorted(totals)},
    }


def persist_optimized_streaming_document_compilation(
    *,
    store: BatchedPostgresCompilerStore,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    source_text: str,
    context: CompilerContext,
    closure_workers: int = 2,
    owner_partitions: int = 2,
) -> tuple[str, ...]:
    """Compile and persist one document in one immutable transaction."""

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
        raise ValueError("declared media capability disagrees with selected adapter")

    build_key_sha256 = _operational_build_key(
        document_ref=document_ref,
        content_sha256=content_sha256,
        canonical_text_sha256=canonical_text_sha256,
        media_adapter_ref=media_adapter_ref,
        context=context,
    )
    with store.transaction() as cursor:
        cached = load_completed_operational_build(
            cursor,
            document_ref=document_ref,
            compiler_contract_ref=FIBRED_OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
        )
        if cached is not None:
            store.persist_occurrence(
                cursor,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                document_ref=document_ref,
                state="reused_compilation",
            )
            return cached

    compilation = compile_document_fibred_operational(
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
        raise ValueError("operational compiler build key disagrees with persistence")
    if artifacts.get("operational_compiler_contract") != (
        FIBRED_OPERATIONAL_COMPILER_CONTRACT
    ):
        raise ValueError("catalogue persistence requires the fibred compiler")
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
    candidate_sets = tuple(artifacts.get("binding_candidate_sets") or ())
    factor_anchors = tuple(artifacts.get("factor_anchors") or ())
    candidate_set_builds = tuple(
        artifacts.get("binding_candidate_set_builds") or ()
    )
    demands = tuple(artifacts.get("resolution_demands") or ())
    meets = _prepare_meets_for_relational_persistence(
        artifacts.get("typed_meets") or ()
    )
    streaming_build = artifacts.get("streaming_semantic_build") or {}
    stage_ledger = dict(artifacts.get("semantic_stage_timing") or {})
    certificate = streaming_build.get("fixed_point_certificate") or {}
    if certificate.get("local_fixed_point") != "reached":
        raise ValueError(
            "only locally fixed-point streaming builds may be persisted"
        )
    if not streaming_build.get("one_reduction_authority"):
        raise ValueError("fibred build requires one reduction authority")
    if not streaming_build.get("reduction_is_not_resolution"):
        raise ValueError("semantic lifecycle must separate reduction and resolution")
    expected_producer_receipt = (
        streaming_build.get("integrated_producer_receipt") or {}
    )
    proposals = tuple(
        row
        for row in streaming_build.get("proposals") or ()
        if isinstance(row, Mapping)
    )

    persistence_started = monotonic_ns()
    with store.savepoint() as cursor:
        stage_started = monotonic_ns()
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
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.token_lexeme",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(canonical_tokens),
            output_nodes=len(canonical_tokens),
            details={
                "token_count": len(canonical_tokens),
                "mention_count": len(
                    artifacts["licensing"].get("mentions") or ()
                ),
                "batched": True,
                "canonical_lock_order": (
                    "lexeme_key_then_document_children"
                ),
            },
        )

        stage_started = monotonic_ns()
        base_factor_revisions = persist_pnf_graph_batched(
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
                resulting_factor_revisions[str(resulting["factor_ref"])] = (
                    revision_ref
                )
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.graph_revision",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(artifacts["pnf_graph"].get("factors") or ()),
            output_nodes=len(base_factor_revisions),
            details={
                "batched": True,
                "refinement_count": len(refinements),
            },
        )

        stage_started = monotonic_ns()
        demand_refs = persist_resolution_artifacts_batched(
            cursor,
            factor_revisions=resulting_factor_revisions,
            demands=demands,
            evidence=tuple(artifacts.get("local_evidence") or ()),
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
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.resolution_binding",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(demands) + len(candidate_sets) + len(meets),
            output_nodes=len(demand_refs),
            details={
                "demand_count": len(demands),
                "candidate_set_count": len(candidate_sets),
                "typed_meet_count": len(meets),
                "resolution_children_batched": True,
            },
        )

        stage_started = monotonic_ns()
        persist_factor_proposal_parents(cursor, proposals)
        lifecycle_counts = persist_semantic_lifecycle_artifacts(
            cursor,
            document_ref=compilation.document_ref,
            artifacts=artifacts,
        )
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.semantic_lifecycle",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(proposals),
            output_nodes=sum(lifecycle_counts.values()),
            details={
                **lifecycle_counts,
                "batched": True,
                "reduction_is_not_resolution": True,
                "memory_learning_deferred": True,
            },
        )

        stage_started = monotonic_ns()
        persisted_producer_receipt = (
            persist_semantic_fibre_artifacts_batched(
                cursor,
                document_ref=compilation.document_ref,
                observation_deltas=tuple(
                    row
                    for row in streaming_build.get("observation_deltas") or ()
                    if isinstance(row, Mapping)
                ),
                proposals=proposals,
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
                    for row in streaming_build.get(
                        "fibre_boundary_obligations"
                    )
                    or ()
                    if isinstance(row, Mapping)
                ),
            )
        )
        if expected_producer_receipt:
            if persisted_producer_receipt.fibre_ledger_ref != str(
                expected_producer_receipt.get("fibre_ledger_ref") or ""
            ):
                raise ValueError(
                    "persisted fibre ledger disagrees with compiler receipt"
                )
            if persisted_producer_receipt.receipt_ref != str(
                expected_producer_receipt.get("receipt_ref") or ""
            ):
                raise ValueError(
                    "persisted producer receipt disagrees with compiler receipt"
                )
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.fibred_ledger",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(proposals),
            output_nodes=len(
                (
                    streaming_build.get("materialized_reduction") or {}
                ).get("factors")
                or ()
            ),
            details={
                "proposal_count": len(proposals),
                "coordinate_count": len(
                    (
                        streaming_build.get("fibred_semantic_build") or {}
                    ).get("semantic_coordinates")
                    or ()
                ),
                "batched": True,
            },
        )

        stage_started = monotonic_ns()
        persist_streaming_semantic_artifacts_batched(
            cursor,
            document_ref=compilation.document_ref,
            streaming_build=streaming_build,
            stage_timing_ledger=stage_ledger,
        )
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres.receipts",
            elapsed_ms=_elapsed_ms(stage_started),
            input_nodes=len(streaming_build.get("solver_receipts") or ()),
            output_nodes=len(streaming_build.get("solver_receipts") or ()),
            details={
                "solver_receipt_count": len(
                    streaming_build.get("solver_receipts") or ()
                ),
                "state_delta_count": len(
                    streaming_build.get("state_deltas") or ()
                ),
                "batched": True,
            },
        )
        stage_ledger = _append_timing(
            stage_ledger,
            document_ref=document_ref,
            stage="postgres_persistence",
            elapsed_ms=_elapsed_ms(persistence_started),
            details={
                "transaction_scope": (
                    "document_immutable_fibred_build"
                ),
                "nested_stage_refs": [
                    row["timing_ref"]
                    for row in stage_ledger.get("timings") or ()
                    if str(row.get("stage") or "").startswith("postgres.")
                ],
                "batched": True,
            },
        )
        persist_stage_timings(
            cursor,
            document_ref=document_ref,
            timings=(
                row
                for row in stage_ledger.get("timings") or ()
                if str(row.get("stage") or "")
                in {"postgres.receipts", "postgres_persistence"}
            ),
        )
        persist_completed_operational_build(
            cursor,
            document_ref=compilation.document_ref,
            compiler_contract_ref=FIBRED_OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
            graph_ref=str(artifacts["pnf_graph"]["graph_ref"]),
            demand_refs=demand_refs,
        )
        return demand_refs


__all__ = ["persist_optimized_streaming_document_compilation"]
