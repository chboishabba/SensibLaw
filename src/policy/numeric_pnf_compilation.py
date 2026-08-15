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
from typing import Any, Mapping

from src.policy.corpus_compilation import DocumentCompilation
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
) -> tuple[str, tuple[str, ...], Mapping[str, int]]:
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
            return (
                graph_ref,
                demand_refs,
                {
                    "document_interface_id": document_interface_id,
                    "interface_cardinality": interface_cardinality,
                    "token_count": counts[0],
                    "region_count": counts[1],
                    "factor_count": counts[2],
                    "object_count": counts[3],
                    "visible_lookup_count": counts[4],
                    "demand_count": len(demand_refs),
                },
            )
    finally:
        connection.close()


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
    )
    graph_ref, demand_refs, counts = _authority_refs(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    if progress is not None and hasattr(progress, "advance"):
        progress.advance(
            amount=1,
            message="numeric_pnf_closed",
            details={
                "graph_ref": graph_ref,
                "demand_count": len(demand_refs),
                **counts,
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
        "parser_receipt": dict(carrier["parser_receipt"]),
        "numeric_pnf_authority": {
            "compiler_contract_ref": NUMERIC_PNF_COMPILER_CONTRACT,
            "parser_execution_contract_ref": STREAMING_SPACY_CONTRACT,
            "run_ref": run_ref,
            "document_ref": document_ref,
            "graph_ref": graph_ref,
            "demand_refs": demand_refs,
            **counts,
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
            # A cached build is an execution-reuse receipt, not a new semantic
            # work observation.  It may be reused under a fresh requested run_ref
            # that has no numeric run identity.  Replay timing/work is measured
            # by the replay benchmark rather than forged as a fresh compile row.
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

    measurement_id = _record_controlled_reuse(
        database_url=database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text_sha256=canonical_text_sha256,
        build_key_sha256=build_key_sha256,
    )
    if progress is not None and hasattr(progress, "finish"):
        progress.finish(
            state="completed",
            details={
                "state": "compiled_numeric_pnf",
                "build_key_sha256": build_key_sha256,
                "graph_ref": graph_ref,
                "demand_ref_count": len(demand_refs),
                "controlled_reuse_measurement_id": measurement_id,
            },
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
