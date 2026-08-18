"""Strict numeric PNF document compilation and publication.

The strict path never reconstructs the legacy document-sized parser mapping,
mention carrier, factor graph, or artifact bundle. Parsing commits numeric
observations exactly once, sentence/region PNF closure runs over those rows, and
publication records the closed document interface plus its residual demands.
"""

from __future__ import annotations

from contextlib import nullcontext
from hashlib import sha256
from pathlib import Path
from time import monotonic_ns
from typing import Any, Mapping

from src.policy.corpus_compilation import DocumentCompilation
from src.runtime.numeric_kernel_progress import (
    NumericKernelProgressSampler,
    numeric_streaming_kernel_progress,
)
from src.runtime.numeric_observability import (
    controlled_reuse_measurement_enabled as _controlled_reuse_measurement_enabled,
    numeric_authority_counts_enabled as _numeric_authority_counts_enabled,
)
from src.storage.postgres.numeric_reuse_measurement import (
    record_numeric_compiler_reuse_measurement,
)
from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
    persist_completed_operational_build,
)
from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy, connect
from src.storage.postgres.streaming_spacy_execution import (
    STREAMING_SPACY_CONTRACT,
    run_streaming_spacy_execution,
)


NUMERIC_PNF_COMPILER_CONTRACT = "numeric-pnf-hyperfabric-compiler:v1"
_NUMERIC_TIMING_FIELDS = (
    "spacy_parser_work_ns",
    "post_parser_worker_work_ns",
    "post_parser_coordinator_ns",
    "post_parser_work_ns",
    "timing_basis",
)


def _artifact_root(
    *,
    run_ref: str,
    checkpoint_dir: str | None,
) -> Path:
    import os

    configured = os.environ.get("SENSIBLAW_TYPED_PARSER_ARTIFACT_ROOT")
    if configured:
        return Path(configured) / run_ref.replace(":", "_")
    if checkpoint_dir:
        return Path(checkpoint_dir) / "numeric-pnf"
    return Path(".tmp") / "numeric-pnf" / run_ref.replace(":", "_")


def _parser_policy(
    *,
    target_chars: int,
    overlap_chars: int,
    cache_docbin: bool = True,
) -> ParserStreamingPolicy:
    return ParserStreamingPolicy(
        target_chars=max(1_024, min(int(target_chars), 32_768)),
        context_chars=max(0, min(int(overlap_chars), 2_048)),
        batch_size=4,
        lease_seconds=180,
        max_repair_depth=2,
        cache_docbin=cache_docbin,
    )


def _authority_refs(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[str, tuple[str, ...], Mapping[str, int | bool]]:
    """Load semantic authority refs; cardinality scans are diagnostics only."""

    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT encode(interface.interface_digest, 'hex'),
                       interface.interface_id,
                       interface.interface_cardinality
                  FROM execution.semantic_pnf_interface AS interface
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id = interface.region_id
                 WHERE region.run_ref = %s
                   AND region.document_ref = %s
                   AND region.region_kind = 10
                   AND region.closure_state = 3
                """,
                (run_ref, document_ref),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("numeric PNF document interface is not closed")
            graph_ref = f"numeric-pnf-interface:{row[0]}"
            document_interface_id = int(row[1])
            interface_cardinality = int(row[2])
            cursor.execute(
                """
                SELECT 'numeric-pnf-demand:' || encode(demand_digest, 'hex')
                  FROM execution.semantic_pnf_demand AS demand
                  JOIN execution.semantic_pnf_region AS region
                    ON region.region_id = demand.source_region_id
                 WHERE region.run_ref = %s
                   AND region.document_ref = %s
                   AND demand.state IN (1, 2, 3)
                 ORDER BY demand.demand_id
                """,
                (run_ref, document_ref),
            )
            demand_refs = tuple(str(item[0]) for item in cursor.fetchall())
            metadata: dict[str, int | bool] = {
                "document_interface_id": document_interface_id,
                "interface_cardinality": interface_cardinality,
                "demand_count": len(demand_refs),
                "diagnostic_counts_measured": False,
            }
            if _numeric_authority_counts_enabled():
                cursor.execute(
                    """
                    SELECT
                        (SELECT count(*)
                           FROM execution.semantic_parser_token
                          WHERE run_ref = %s AND document_ref = %s
                            AND representation_version = 2),
                        (SELECT count(*)
                           FROM execution.semantic_pnf_region
                          WHERE run_ref = %s AND document_ref = %s),
                        (SELECT count(*)
                           FROM execution.semantic_pnf_factor AS factor
                           JOIN execution.semantic_pnf_region AS region
                             ON region.region_id = factor.region_id
                          WHERE region.run_ref = %s
                            AND region.document_ref = %s),
                        (SELECT count(*)
                           FROM execution.semantic_pnf_object AS object
                           JOIN execution.semantic_pnf_region AS region
                             ON region.region_id = object.region_id
                          WHERE region.run_ref = %s
                            AND region.document_ref = %s),
                        (SELECT count(*)
                           FROM execution.semantic_pnf_visible_lookup AS visible
                           JOIN execution.semantic_pnf_interface AS interface
                             ON interface.interface_id = visible.interface_id
                           JOIN execution.semantic_pnf_region AS region
                             ON region.region_id = interface.region_id
                          WHERE region.run_ref = %s
                            AND region.document_ref = %s)
                    """,
                    (
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                        run_ref,
                        document_ref,
                    ),
                )
                counts = tuple(int(value) for value in cursor.fetchone())
                metadata.update(
                    {
                        "token_count": counts[0],
                        "region_count": counts[1],
                        "factor_count": counts[2],
                        "object_count": counts[3],
                        "visible_lookup_count": counts[4],
                        "diagnostic_counts_measured": True,
                    }
                )
            return graph_ref, demand_refs, metadata
    finally:
        connection.close()


def _progress_observer(progress: Any | None):
    """Adapt one active ``PhaseHandle`` to the streaming observation callback."""

    if progress is None or not hasattr(progress, "heartbeat"):
        return None

    def observe(payload: Mapping[str, Any]) -> None:
        details = dict(payload)
        message = str(details.get("current_kernel") or "numeric_pnf_compilation")
        progress.heartbeat(message=message, details=details)

    return observe


def _observe_kernel(
    progress: Any | None,
    *,
    kernel: str,
    state: str,
    elapsed_ns: int | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    if progress is None or not hasattr(progress, "heartbeat"):
        return
    payload: dict[str, Any] = {
        "current_kernel": kernel,
        "kernel_state": state,
        **dict(details or {}),
    }
    if elapsed_ns is not None:
        payload["kernel_elapsed_ns"] = int(elapsed_ns)
    progress.heartbeat(message=kernel, details=payload)


def compile_numeric_pnf_document(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    content_sha256: str,
    media_type: str,
    canonical_text: str,
    canonical_text_sha256: str,
    media_adapter_ref: str,
    parser_contract_ref: str,
    build_key_sha256: str,
    parser_workers: int,
    parser_target_chars: int,
    parser_overlap_chars: int,
    parser_checkpoint_dir: str | None,
    progress: Any | None = None,
) -> DocumentCompilation:
    observer = _progress_observer(progress)
    with numeric_streaming_kernel_progress(observer):
        with NumericKernelProgressSampler(
            database_url=database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            observer=observer,
            interval_seconds=30.0,
        ):
            carrier = run_streaming_spacy_execution(
                database_url=database_url,
                run_ref=run_ref,
                document_ref=document_ref,
                canonical_text=canonical_text,
                parser_contract_ref=parser_contract_ref,
                artifact_root=_artifact_root(
                    run_ref=run_ref,
                    checkpoint_dir=parser_checkpoint_dir,
                ),
                worker_count=parser_workers,
                policy=_parser_policy(
                    target_chars=parser_target_chars,
                    overlap_chars=parser_overlap_chars,
                ),
                progress_observer=observer,
            )
    parser_receipt = dict(carrier["parser_receipt"])
    timing_details = {
        key: parser_receipt[key]
        for key in _NUMERIC_TIMING_FIELDS
        if key in parser_receipt
    }

    authority_started = monotonic_ns()
    _observe_kernel(progress, kernel="numeric_authority_extraction", state="started")
    try:
        graph_ref, demand_refs, authority_metadata = _authority_refs(
            database_url,
            run_ref=run_ref,
            document_ref=document_ref,
        )
    except BaseException as error:
        _observe_kernel(
            progress,
            kernel="numeric_authority_extraction",
            state="failed",
            elapsed_ns=monotonic_ns() - authority_started,
            details={"kernel_error_type": type(error).__name__, "kernel_error": str(error)},
        )
        raise
    _observe_kernel(
        progress,
        kernel="numeric_authority_extraction",
        state="completed",
        elapsed_ns=monotonic_ns() - authority_started,
        details={
            "graph_ref": graph_ref,
            "demand_count": len(demand_refs),
            **timing_details,
            **authority_metadata,
        },
    )
    artifacts: dict[str, Any] = {
        "canonical_text_sha256": canonical_text_sha256,
        "source_normalisation": {
            "adapter_ref": media_adapter_ref,
            "source_media_type": media_type,
            "authority": "normalisation_only",
        },
        "build_key_sha256": build_key_sha256,
        "parser_receipt": parser_receipt,
        "numeric_execution_timing": timing_details,
        "numeric_pnf_authority": {
            "compiler_contract_ref": NUMERIC_PNF_COMPILER_CONTRACT,
            "parser_execution_contract_ref": STREAMING_SPACY_CONTRACT,
            "run_ref": run_ref,
            "document_ref": document_ref,
            "graph_ref": graph_ref,
            "demand_refs": demand_refs,
            **authority_metadata,
            "representation": "numeric_postgresql_hyperfabric",
            "legacy_document_materialisation": False,
            "world_resolution_deferred": True,
        },
        "phase_boundary": {
            "completed": (
                "numeric_parser",
                "sentence_closure",
                "regional_closure",
                "document_interface",
                "demand_planning",
            ),
            "network_performed": False,
            "cross_document_identity_closed": False,
            "legacy_projection_invoked": False,
        },
    }
    return DocumentCompilation(
        document_ref=document_ref,
        content_sha256=content_sha256,
        media_type=media_type,
        artifacts=artifacts,
    )


def _record_controlled_reuse(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text_sha256: str,
    build_key_sha256: str,
) -> int:
    return record_numeric_compiler_reuse_measurement(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text_sha256=canonical_text_sha256,
        compiler_config_sha256=build_key_sha256,
    )


def persist_numeric_pnf_document(
    *,
    store: Any,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    canonical_text: str,
    canonical_text_sha256: str,
    media_adapter_ref: str,
    context: Any,
    build_key_sha256: str,
    database_url: str,
    run_ref: str,
    parser_workers: int,
    parser_target_chars: int,
    parser_overlap_chars: int,
    parser_checkpoint_dir: str | None,
    progress: Any | None = None,
) -> tuple[str, ...]:
    document_ref = str(entry["document_ref"])
    media_type = str(entry["media_type"])
    content_sha256 = str(entry["content_sha256"])
    with store.transaction() as cursor:
        cached = load_completed_operational_build(
            cursor,
            document_ref=document_ref,
            compiler_contract_ref=NUMERIC_PNF_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
        )
        if cached is not None:
            store.persist_occurrence(
                cursor,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                document_ref=document_ref,
                state="reused_numeric_pnf",
            )
            return cached
        store.persist_source_document(
            cursor,
            document_ref=document_ref,
            media_type=media_type,
            content_sha256=content_sha256,
            source_bytes=source_bytes,
            canonical_text=canonical_text,
            adapter_ref=media_adapter_ref,
            adapter_version=context.media_normalization_ref,
            compiler_context_ref=context.context_ref,
            normalization_ref=context.media_normalization_ref,
        )

    progress_stage = (
        progress.stage(
            "numeric_pnf_compilation",
            details={"build_key_sha256": build_key_sha256},
            advance_outer=False,
        )
        if progress is not None and hasattr(progress, "stage")
        else nullcontext(None)
    )
    with progress_stage:
        compilation = compile_numeric_pnf_document(
            database_url=database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            content_sha256=content_sha256,
            media_type=media_type,
            canonical_text=canonical_text,
            canonical_text_sha256=canonical_text_sha256,
            media_adapter_ref=media_adapter_ref,
            parser_contract_ref=str(context.annotation_backend_ref),
            build_key_sha256=build_key_sha256,
            parser_workers=parser_workers,
            parser_target_chars=parser_target_chars,
            parser_overlap_chars=parser_overlap_chars,
            parser_checkpoint_dir=parser_checkpoint_dir,
            progress=progress,
        )
        authority = compilation.artifacts["numeric_pnf_authority"]
        graph_ref = str(authority["graph_ref"])
        demand_refs = tuple(str(value) for value in authority["demand_refs"])

        publication_started = monotonic_ns()
        _observe_kernel(progress, kernel="operational_build_publication", state="started")
        try:
            with store.savepoint() as cursor:
                persist_completed_operational_build(
                    cursor,
                    document_ref=document_ref,
                    compiler_contract_ref=NUMERIC_PNF_COMPILER_CONTRACT,
                    build_key_sha256=build_key_sha256,
                    graph_ref=graph_ref,
                    demand_refs=demand_refs,
                )
                store.persist_occurrence(
                    cursor,
                    corpus_ref=corpus_ref,
                    relative_path=relative_path,
                    document_ref=document_ref,
                    state="compiled_numeric_pnf",
                )
        except BaseException as error:
            _observe_kernel(
                progress,
                kernel="operational_build_publication",
                state="failed",
                elapsed_ns=monotonic_ns() - publication_started,
                details={
                    "kernel_error_type": type(error).__name__,
                    "kernel_error": str(error),
                },
            )
            raise
        _observe_kernel(
            progress,
            kernel="operational_build_publication",
            state="completed",
            elapsed_ns=monotonic_ns() - publication_started,
        )

        from src.policy.numeric_semantic_receipt_execution import (
            persist_completed_numeric_semantic_receipt,
        )

        receipt_started = monotonic_ns()
        _observe_kernel(progress, kernel="semantic_receipt_publication", state="started")
        try:
            persist_completed_numeric_semantic_receipt(
                database_url=database_url,
                document_ref=document_ref,
                canonical_text_sha256=canonical_text_sha256,
                parser_contract_ref=str(context.annotation_backend_ref),
                build_key_sha256=build_key_sha256,
                compiler_contract_ref=NUMERIC_PNF_COMPILER_CONTRACT,
            )
        except BaseException as error:
            _observe_kernel(
                progress,
                kernel="semantic_receipt_publication",
                state="failed",
                elapsed_ns=monotonic_ns() - receipt_started,
                details={
                    "kernel_error_type": type(error).__name__,
                    "kernel_error": str(error),
                },
            )
            raise
        _observe_kernel(
            progress,
            kernel="semantic_receipt_publication",
            state="completed",
            elapsed_ns=monotonic_ns() - receipt_started,
        )

        measurement_id: int | None = None
        if _controlled_reuse_measurement_enabled():
            measurement_started = monotonic_ns()
            _observe_kernel(progress, kernel="controlled_reuse_measurement", state="started")
            try:
                measurement_id = _record_controlled_reuse(
                    database_url=database_url,
                    run_ref=run_ref,
                    document_ref=document_ref,
                    canonical_text_sha256=canonical_text_sha256,
                    build_key_sha256=build_key_sha256,
                )
            except BaseException as error:
                _observe_kernel(
                    progress,
                    kernel="controlled_reuse_measurement",
                    state="failed",
                    elapsed_ns=monotonic_ns() - measurement_started,
                    details={
                        "kernel_error_type": type(error).__name__,
                        "kernel_error": str(error),
                    },
                )
                raise
            _observe_kernel(
                progress,
                kernel="controlled_reuse_measurement",
                state="completed",
                elapsed_ns=monotonic_ns() - measurement_started,
                details={"controlled_reuse_measurement_id": measurement_id},
            )

        if progress is not None and hasattr(progress, "advance"):
            details: dict[str, Any] = {
                "state": "compiled_numeric_pnf",
                "build_key_sha256": build_key_sha256,
                "graph_ref": graph_ref,
                "demand_ref_count": len(demand_refs),
                **dict(compilation.artifacts.get("numeric_execution_timing") or {}),
            }
            if measurement_id is not None:
                details["controlled_reuse_measurement_id"] = measurement_id
            # Exactly one outer completion for this strict numeric document, and
            # only after both operational-build and semantic-receipt publication.
            progress.advance(
                amount=1,
                message="numeric_pnf_completed",
                details=details,
            )
    return demand_refs


def canonical_text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "NUMERIC_PNF_COMPILER_CONTRACT",
    "canonical_text_sha256",
    "compile_numeric_pnf_document",
    "persist_numeric_pnf_document",
]
