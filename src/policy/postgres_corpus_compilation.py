"""PostgreSQL-backed corpus compilation with no semantic JSON projections."""

from __future__ import annotations

from contextlib import nullcontext
import json
import hashlib
import inspect
import os
import sys
from pathlib import Path
import tempfile
from time import monotonic_ns
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from itertools import islice
from typing import Any, Callable, Iterator, Mapping, Sequence

from tqdm.auto import tqdm

from src.ingestion.media_adapter import HtmlDocumentMediaAdapter
from src.pnf.document_fibres import DOCUMENT_FIBRE_CONTRACT, DocumentFibrePolicy
from src.policy.carriers.canonical import canonical_sha256
from src.policy.algebra.revision_identity import factor_revision_ref
from src.policy.artifact_projection import (
    ArtifactManifestReader,
    iter_verified_records,
)
from src.policy.manifest_stream_validation import ManifestParentClosureValidator
from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    DOCUMENT_COMPILE_STAGE_COUNT,
)
from src.runtime.document_stage_metrics import stage_measure_declaration
from src.runtime.active_document_resources import (
    ActiveDocumentResourceGuard,
    GuardedDocumentProgress,
)
from src.runtime.execution_resource_ledger import ExecutionResourceLedger
from src.runtime.progress import PhaseRecorder
from src.runtime.strict_postgres_execution import StrictExecutionError
from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans
from src.storage.postgres import PersistedCompilation, PostgresCompilerStore
from src.storage.postgres.binding_candidate_store import persist_binding_candidate_sets
from src.storage.postgres.factor_revision_store import persist_factor_revision
from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
    persist_completed_operational_build,
)
from src.storage.postgres.semantic_store import (
    persist_pnf_graph,
    persist_resolution_artifacts,
)
from src.storage.postgres.span_store import persist_licensed_spans


PreparedSource = tuple[bytes, str]
CompilationDocumentExecutor = Callable[..., tuple[str, ...]]
COMPILATION_STATE_SCHEMA_VERSION = "sl.postgres_corpus_compilation_state.v0_1"


def _record_batches(
    records: Sequence[tuple[str, int, int]], *, batch_size: int = 256
) -> Iterator[Sequence[tuple[str, int, int]]]:
    """Replay ordered records in execution-only bounded batches."""

    iterator = iter(records)
    while batch := tuple(islice(iterator, batch_size)):
        yield batch


def _is_manifest_descriptor(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("representation") == "manifest"


def _descriptor_metadata(
    reader: ArtifactManifestReader, descriptor: Mapping[str, Any]
) -> dict[str, Any]:
    """Read only descriptor scalar fields; the write pass remains verified.

    Manifest records place repeated families ahead of scalar metadata by stable
    field ordering.  This bounded preflight avoids retaining those families
    merely to discover their header.
    """

    metadata: dict[str, Any] = {}
    for batch in reader.iter_records(str(descriptor["artifact_key"]), 256):
        for record in batch:
            if record.get("reconstruction") == "mapping_scalar":
                metadata[str(record["field"])] = record.get("value")
    return metadata


def _iter_descriptor_family(
    reader: ArtifactManifestReader,
    descriptor: Mapping[str, Any],
    family: str,
) -> Iterator[tuple[Mapping[str, Any], ...]]:
    """Yield one family in native 256-row batches and verify at EOF."""

    for batch in iter_verified_records(reader, descriptor, batch_size=256):
        rows = tuple(
            row["value"]
            for row in batch
            if row.get("family") == family and isinstance(row.get("value"), Mapping)
        )
        if rows:
            yield rows


def _verify_descriptor(
    reader: ArtifactManifestReader, descriptor: Mapping[str, Any]
) -> None:
    """Verify a descriptor whose rows are not persisted by this boundary."""

    for _batch in iter_verified_records(reader, descriptor, batch_size=256):
        pass


def _persist_streamed_candidate_builds(
    cursor: Any, rows: Sequence[Mapping[str, Any]]
) -> None:
    """Persist explicit build descriptors after their candidate sets exist."""

    payloads = []
    for row in rows:
        identity = {
            "generator_build_ref": row["generator_build_ref"],
            "reference_factor_revision_ref": row["reference_factor_revision_ref"],
            "document_pnf_index_ref": row.get("document_pnf_index_ref"),
            "accessibility_declaration_ref": row["accessibility_declaration_ref"],
            "compatibility_declaration_ref": row["compatibility_declaration_ref"],
            "referential_type_ref": row["referential_type_ref"],
        }
        payloads.append(
            (
                str(row["generator_build_ref"]),
                str(row["candidate_set_ref"]),
                str(row["reference_factor_revision_ref"]),
                str(row.get("document_pnf_index_ref") or ""),
                str(row["accessibility_declaration_ref"]),
                str(row["compatibility_declaration_ref"]),
                str(row["referential_type_ref"]),
                canonical_sha256(identity),
            )
        )
    if payloads:
        cursor.executemany(
            """
            INSERT INTO execution.binding_candidate_set_build
                (generator_build_ref, candidate_set_ref,
                 reference_factor_revision_ref, document_pnf_index_ref,
                 accessibility_declaration_ref, compatibility_declaration_ref,
                 referential_type_ref, build_key_sha256, build_state_ref)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'completed')
            ON CONFLICT (generator_build_ref) DO UPDATE SET
                candidate_set_ref = EXCLUDED.candidate_set_ref,
                reference_factor_revision_ref = EXCLUDED.reference_factor_revision_ref,
                document_pnf_index_ref = EXCLUDED.document_pnf_index_ref,
                accessibility_declaration_ref = EXCLUDED.accessibility_declaration_ref,
                compatibility_declaration_ref = EXCLUDED.compatibility_declaration_ref,
                referential_type_ref = EXCLUDED.referential_type_ref,
                build_key_sha256 = EXCLUDED.build_key_sha256
            """,
            payloads,
        )


def _persist_streamed_candidate_links(
    cursor: Any, *, kind: str, rows: Sequence[Mapping[str, Any]]
) -> None:
    """Write generic candidate-set links from a verified descriptor batch."""

    specifications = {
        "refinement": ("refinement_ref", "resolution.refinement_candidate_set"),
        "meet": ("meet_ref", "resolution.meet_candidate_set"),
        "demand": ("demand_ref", "resolution.demand_candidate_set"),
    }
    source_column, table = specifications[kind]
    links = [
        (str(row[source_column]), str(candidate_set_ref))
        for row in rows
        for candidate_set_ref in row.get("candidate_set_refs") or ()
    ]
    if links:
        cursor.executemany(
            f"INSERT INTO {table} ({source_column}, candidate_set_ref) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            links,
        )


def _compile_document_postgres_worker(
    *,
    database_url: str,
    progress: bool,
    store_kwargs: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile one document on an isolated PostgreSQL connection.

    The canonical operational compiler remains the document executor; this
    wrapper only supplies worker-local persistence and returns a serializable
    checkpoint result to the scheduler.
    """
    store = PostgresCompilerStore.connect(database_url)
    try:
        document_ref = str(store_kwargs["document_ref"])
        worker_ref = str(store_kwargs["worker_ref"])
        relative_path = str(store_kwargs["relative_path"])
        try:
            cached = None
            with store.transaction() as cursor:
                cached = load_completed_operational_build(
                    cursor,
                    document_ref=document_ref,
                    compiler_contract_ref=str(
                        store_kwargs["document_executor_contract_ref"]
                    ),
                    build_key_sha256=str(store_kwargs["build_key_sha256"]),
                )
            if cached is not None:
                with store.transaction() as cursor:
                    store.persist_occurrence(
                        cursor,
                        corpus_ref=str(store_kwargs["corpus_ref"]),
                        relative_path=relative_path,
                        document_ref=document_ref,
                        state="reused_compilation",
                    )
                return {
                    "document_ref": document_ref,
                    "relative_path": relative_path,
                    "state": "reused_compilation",
                    "demand_refs": list(cached),
                    "worker": worker_ref,
                    "build_key_sha256": str(store_kwargs["build_key_sha256"]),
                }
            started_ns = monotonic_ns()
            worker_progress = (
                PhaseRecorder(stream=sys.stderr, json_lines=False)
                if progress is not None
                else None
            )
            with (
                worker_progress.phase(
                    f"postgres_{store_kwargs['execution_phase']}_document_compile",
                    total=DOCUMENT_COMPILE_STAGE_COUNT + 1,
                    subject_ref=relative_path,
                    message="document compile",
                    worker=worker_ref,
                    details={
                        "document_ref": document_ref,
                        "relative_path": relative_path,
                        "build_key_sha256": str(store_kwargs["build_key_sha256"]),
                        "execution_phase": str(store_kwargs["execution_phase"]),
                    },
                    heartbeat_seconds=30.0,
                )
                if worker_progress is not None
                else nullcontext(None)
            ) as document_progress:
                document_guard = ActiveDocumentResourceGuard(
                    document_ref=document_ref
                )
                guarded_progress = (
                    GuardedDocumentProgress(document_progress, document_guard)
                    if document_progress is not None
                    else None
                )
                refs = store_kwargs["document_executor"](
                    store=store,
                    corpus_ref=str(store_kwargs["corpus_ref"]),
                    relative_path=relative_path,
                    entry=store_kwargs["entry"],
                    source_bytes=store_kwargs["source_bytes"],
                    source_text=store_kwargs["source_text"],
                    context=store_kwargs["context"],
                    execution_phase=str(store_kwargs["execution_phase"]),
                    batch_index=int(store_kwargs["batch_index"]),
                    closure_workers=int(store_kwargs["closure_workers"]),
                    owner_partitions=int(store_kwargs["owner_partitions"]),
                    parser_workers=int(store_kwargs["parser_workers"]),
                    parser_limit_chars=int(store_kwargs["parser_limit_chars"]),
                    parser_target_chars=int(store_kwargs["parser_target_chars"]),
                    parser_overlap_chars=int(store_kwargs["parser_overlap_chars"]),
                    parser_checkpoint_dir=store_kwargs["parser_checkpoint_dir"],
                    progress=guarded_progress,
                    execution_strategy_ref=str(
                        store_kwargs.get("execution_strategy_ref")
                        or "local-compatibility-replay"
                    ),
                    database_url=database_url,
                    strict_run_ref=str(
                        store_kwargs.get("strict_run_ref") or f"strict:{document_ref}"
                    ),
                )
            return {
                "document_ref": document_ref,
                "relative_path": relative_path,
                "state": "compiled",
                "demand_refs": list(refs),
                "worker": worker_ref,
                "build_key_sha256": str(store_kwargs["build_key_sha256"]),
                "elapsed_ms": max(0, (monotonic_ns() - started_ns) // 1_000_000),
            }
        except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
            if str(
                store_kwargs.get("execution_strategy_ref") or ""
            ) == "postgresql-leased-exact-execution:v1" and isinstance(
                error, StrictExecutionError
            ):
                raise
            with store.transaction() as cursor:
                failure_ref = store.persist_failure(
                    cursor,
                    target_ref=document_ref,
                    phase_ref="local_compile",
                    error=error,
                )
            return {
                "document_ref": document_ref,
                "relative_path": relative_path,
                "state": "failed",
                "failure_ref": failure_ref,
                "error_type": type(error).__name__,
                "error": str(error),
                "worker": worker_ref,
            }
    finally:
        store.close()


def _canonical_source_coordinates(
    *, media_type: str, source_text: str, source_ref: str
) -> tuple[str, str, str]:
    """Return the deterministic text coordinate system used by the compiler."""

    if media_type == "text/html":
        canonical_text = (
            HtmlDocumentMediaAdapter(source_artifact_ref=source_ref)
            .adapt(source_text)
            .text
        )
        adapter_ref = "media:html:v0_1"
    else:
        canonical_text = source_text
        adapter_ref = "media:utf8-text:v0_1"
    if not canonical_text:
        raise ValueError("source normalisation produced empty canonical text")
    return (
        canonical_text,
        hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
        adapter_ref,
    )


def _operational_document_ref(
    *,
    source_content_sha256: str,
    canonical_text_sha256: str,
    media_type: str,
    media_adapter_ref: str,
    context: CompilerContext,
) -> str:
    """Derive immutable document identity from source and canonical coordinates."""

    return "document:" + canonical_sha256(
        {
            "source_content_sha256": source_content_sha256,
            "canonical_text_sha256": canonical_text_sha256,
            "media_type": media_type,
            "media_adapter_ref": media_adapter_ref,
            "media_normalization_ref": context.media_normalization_ref,
            "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
        }
    )


def _prepare_operational_manifest(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    context: CompilerContext,
) -> tuple[dict[str, Any], dict[str, PreparedSource]]:
    """Bind a raw inventory to the active canonical-coordinate contract.

    The source inventory remains represented by ``source_document_ref``. The
    operational ``document_ref`` changes whenever canonical text, the selected
    media adapter, or the compiler coordinate contract changes. This prevents a
    v0.8 rebuild from colliding with a v0.7 document row whose canonical pointer
    addressed raw HTML.
    """

    prepared_sources: dict[str, PreparedSource] = {}
    prepared_documents: list[dict[str, Any]] = []
    for raw_entry in manifest.get("ordered_documents") or ():
        entry = dict(raw_entry)
        if str(entry.get("status") or "") == "inventoried":
            relative_path = str(entry["relative_path"])
            source_document_ref = str(entry["document_ref"])
            try:
                source_bytes = (root / relative_path).read_bytes()
                source_text = source_bytes.decode("utf-8")
                canonical_text, canonical_sha, media_adapter_ref = (
                    _canonical_source_coordinates(
                        media_type=str(entry["media_type"]),
                        source_text=source_text,
                        source_ref=f"source-content:{entry['content_sha256']}",
                    )
                )
            except (OSError, UnicodeDecodeError, ValueError):
                # The compile loop records the concrete failure receipt. Keeping
                # the raw inventory identity here preserves a truthful manifest.
                pass
            else:
                del canonical_text
                entry.update(
                    {
                        "source_document_ref": source_document_ref,
                        "canonical_text_sha256": canonical_sha,
                        "media_adapter_ref": media_adapter_ref,
                        "document_ref": _operational_document_ref(
                            source_content_sha256=str(entry["content_sha256"]),
                            canonical_text_sha256=canonical_sha,
                            media_type=str(entry["media_type"]),
                            media_adapter_ref=media_adapter_ref,
                            context=context,
                        ),
                    }
                )
                prepared_sources[relative_path] = (source_bytes, source_text)
        prepared_documents.append(entry)

    row = dict(manifest)
    row["ordered_documents"] = prepared_documents
    row["compiler_contract_ref"] = OPERATIONAL_COMPILER_CONTRACT
    corpus_identity = {
        "root_ref": row["root_ref"],
        "compiler_context_ref": row["compiler_context_ref"],
        "compiler_contract_ref": OPERATIONAL_COMPILER_CONTRACT,
        "ordered_documents": prepared_documents,
        "ignored_entries": row.get("ignored_entries") or (),
        "unsupported_entries": row.get("unsupported_entries") or (),
        "inventory_failures": row.get("inventory_failures") or (),
    }
    row["corpus_ref"] = "corpus:" + canonical_sha256(corpus_identity)
    row_without_digest = {
        key: value for key, value in row.items() if key != "manifest_sha256"
    }
    row["manifest_sha256"] = canonical_sha256(row_without_digest)
    return row, prepared_sources


def _operational_build_key(
    *,
    document_ref: str,
    content_sha256: str,
    canonical_text_sha256: str,
    media_adapter_ref: str,
    context: CompilerContext,
    parser_workers: int = 2,
    parser_limit_chars: int = 1_000_000,
    parser_target_chars: int = 400_000,
    parser_overlap_chars: int = 8_192,
) -> str:
    parser_policy = DocumentFibrePolicy(
        workers=parser_workers,
        parser_limit_chars=parser_limit_chars,
        target_chars=parser_target_chars,
        overlap_chars=parser_overlap_chars,
    )
    return canonical_sha256(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "canonical_text_sha256": canonical_text_sha256,
            "media_adapter_ref": media_adapter_ref,
            "context": context.to_dict(),
            "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
            "document_fibre_contract": DOCUMENT_FIBRE_CONTRACT,
            "document_fibre_policy": parser_policy.to_dict(),
            "closure_workers_semantic_effect": "none",
            "owner_partitions_semantic_effect": "none",
        }
    )


def _prepare_meets_for_relational_persistence(
    meets: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Keep candidate-set refs distinct from evidence-table references."""

    prepared: list[dict[str, Any]] = []
    for row in meets:
        item = dict(row)
        evidence_refs = tuple(str(ref) for ref in item.get("evidence_refs") or ())
        candidate_set_refs = set(
            str(ref) for ref in item.get("candidate_set_refs") or ()
        )
        candidate_set_refs.update(
            ref for ref in evidence_refs if ref.startswith("binding-candidate-set:")
        )
        item["evidence_refs"] = [
            ref for ref in evidence_refs if not ref.startswith("binding-candidate-set:")
        ]
        if candidate_set_refs:
            item["candidate_set_refs"] = sorted(candidate_set_refs)
        prepared.append(item)
    return tuple(prepared)


def _validated_canonical_tokens(
    *, artifacts: Mapping[str, Any], expected_text: str, expected_sha256: str
) -> tuple[tuple[str, int, int], ...]:
    """Validate that every persisted span and token uses compiler coordinates."""

    canonical_text = artifacts.get("canonical_text")
    if canonical_text != expected_text:
        raise ValueError(
            "operational compiler canonical text disagrees with persistence"
        )
    canonical_text_sha256 = str(artifacts.get("canonical_text_sha256") or "")
    if canonical_text_sha256 != expected_sha256:
        raise ValueError(
            "operational compiler canonical text hash disagrees with persistence"
        )
    tokens = tuple(tokenize_canonical_with_spans(expected_text))
    mentions = tuple((artifacts.get("licensing") or {}).get("mentions") or ())
    for mention in mentions:
        start_char = int(mention["start_char"])
        end_char = int(mention["end_char"])
        start_token = int(mention["start_token"])
        end_token = int(mention["end_token"])
        if not (0 <= start_char < end_char <= len(expected_text)):
            raise ValueError("licensed mention is outside canonical text coordinates")
        if not (0 <= start_token < end_token <= len(tokens)):
            raise ValueError("licensed mention is outside canonical token coordinates")
        observed_surface = expected_text[start_char:end_char]
        if observed_surface != str(mention["canonical_surface"]):
            raise ValueError("licensed mention surface disagrees with canonical text")
        token_start = tokens[start_token][1]
        token_end = tokens[end_token - 1][2]
        if token_start != start_char or token_end != end_char:
            raise ValueError("licensed mention character and token ranges disagree")
    return tokens


def _factor_producer_contract(factor: Mapping[str, Any]) -> str:
    metadata = factor.get("metadata") if isinstance(factor, Mapping) else None
    if not isinstance(metadata, Mapping):
        return "unknown"
    return str(
        metadata.get("producer_contract")
        or metadata.get("composition_contract_ref")
        or metadata.get("operational_compiler_contract")
        or metadata.get("factor_producer_contract")
        or "unknown"
    )


def _parent_closure_violation_message(
    *,
    document_ref: str,
    relative_path: str,
    execution_phase: str,
    batch_index: int,
    child_table: str,
    child_ref: str,
    parent_table: str,
    parent_column: str,
    missing_parent_ref: str,
    semantic_artifact_type: str,
    producer_contract: str,
    persistence_stage: str = "postgres_savepoint",
    detail: str | None = None,
) -> str:
    fields = {
        "document_ref": document_ref,
        "relative_path": relative_path,
        "stage": execution_phase,
        "batch_index": batch_index,
        "persistence_stage": persistence_stage,
        "child_table": child_table,
        "child_ref": child_ref,
        "parent_table": parent_table,
        "parent_column": parent_column,
        "missing_parent_ref": missing_parent_ref,
        "semantic_artifact_type": semantic_artifact_type,
        "producer_contract": producer_contract,
    }
    if detail:
        fields["detail"] = detail
    return "document parent closure violation: " + " ".join(
        f"{key}={value}" for key, value in fields.items()
    )


def _validate_document_parent_closure(
    *,
    document_ref: str,
    relative_path: str,
    execution_phase: str,
    batch_index: int,
    base_factor_revisions: Mapping[str, str],
    resulting_factor_revisions: Mapping[str, str],
    candidate_sets: Sequence[Mapping[str, Any]],
    factor_anchors: Sequence[Mapping[str, Any]],
    refinements: Sequence[Mapping[str, Any]],
    demands: Sequence[Mapping[str, Any]],
) -> None:
    available_factor_revisions = {
        str(ref_revision)
        for ref_revision in (
            *base_factor_revisions.values(),
            *resulting_factor_revisions.values(),
        )
        if ref_revision
    }
    for refinement in refinements:
        prior = refinement.get("prior_factor")
        resulting = refinement.get("resulting_factor")
        if not isinstance(prior, Mapping) or not isinstance(resulting, Mapping):
            continue
        prior_revision_ref = factor_revision_ref(prior)
        if prior_revision_ref not in available_factor_revisions:
            raise ValueError(
                _parent_closure_violation_message(
                    document_ref=document_ref,
                    relative_path=relative_path,
                    execution_phase=execution_phase,
                    batch_index=batch_index,
                    child_table="resolution.refinement",
                    child_ref=str(refinement.get("refinement_ref") or ""),
                    parent_table="algebra.factor_revision",
                    parent_column="factor_revision_ref",
                    missing_parent_ref=prior_revision_ref,
                    semantic_artifact_type="factor_refinement",
                    producer_contract=_factor_producer_contract(prior),
                )
            )
    for candidate_set in candidate_sets:
        reference_factor_ref = str(candidate_set.get("reference_factor_ref") or "")
        reference_revision_ref = base_factor_revisions.get(reference_factor_ref)
        if reference_revision_ref is None:
            raise ValueError(
                _parent_closure_violation_message(
                    document_ref=document_ref,
                    relative_path=relative_path,
                    execution_phase=execution_phase,
                    batch_index=batch_index,
                    child_table="resolution.binding_candidate_set",
                    child_ref=str(candidate_set.get("candidate_set_ref") or ""),
                    parent_table="algebra.factor_revision",
                    parent_column="reference_factor_revision_ref",
                    missing_parent_ref=str(
                        candidate_set.get("reference_factor_revision_ref") or ""
                    ),
                    semantic_artifact_type="binding_candidate_set",
                    producer_contract=_factor_producer_contract(candidate_set),
                )
            )
    for factor_anchor in factor_anchors:
        factor_ref = str(factor_anchor.get("factor_ref") or "")
        anchor_revision_ref = base_factor_revisions.get(factor_ref)
        if anchor_revision_ref is None:
            raise ValueError(
                _parent_closure_violation_message(
                    document_ref=document_ref,
                    relative_path=relative_path,
                    execution_phase=execution_phase,
                    batch_index=batch_index,
                    child_table="pnf.factor_anchor",
                    child_ref=str(factor_anchor.get("factor_revision_ref") or ""),
                    parent_table="algebra.factor_revision",
                    parent_column="factor_revision_ref",
                    missing_parent_ref=str(
                        factor_anchor.get("factor_revision_ref") or ""
                    ),
                    semantic_artifact_type="factor_anchor",
                    producer_contract=_factor_producer_contract(factor_anchor),
                )
            )
    for demand in demands:
        factor_ref = str(demand.get("factor_ref") or "")
        demand_revision_ref = resulting_factor_revisions.get(factor_ref)
        if demand_revision_ref is None:
            raise ValueError(
                _parent_closure_violation_message(
                    document_ref=document_ref,
                    relative_path=relative_path,
                    execution_phase=execution_phase,
                    batch_index=batch_index,
                    child_table="resolution.demand",
                    child_ref=str(demand.get("demand_ref") or ""),
                    parent_table="algebra.factor_revision",
                    parent_column="factor_revision_ref",
                    missing_parent_ref=str(demand.get("factor_revision_ref") or ""),
                    semantic_artifact_type="resolution_demand",
                    producer_contract=_factor_producer_contract(demand),
                )
            )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json_payload = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write(json_payload + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    parent_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _load_compilation_state(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _save_compilation_state(path: Path | None, payload: Mapping[str, Any]) -> None:
    if path is None:
        return
    _atomic_write_json(path, payload)


def persist_document_compilation(
    *,
    store: PostgresCompilerStore,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    source_text: str,
    context: CompilerContext,
    execution_phase: str,
    batch_index: int,
    closure_workers: int = 1,
    owner_partitions: int = 1,
    parser_workers: int = 2,
    parser_limit_chars: int = 1_000_000,
    parser_target_chars: int = 400_000,
    parser_overlap_chars: int = 8_192,
    parser_checkpoint_dir: str | None = None,
    progress: Any | None = None,
    resource_ledger: ExecutionResourceLedger | None = None,
    execution_strategy_ref: str = "local-compatibility-replay",
    database_url: str | None = None,
    strict_run_ref: str | None = None,
) -> tuple[str, ...]:
    """Compile and persist one document transactionally.

    Raw source bytes remain source evidence. The compiler-produced canonical
    projection is the only coordinate system used by token, span, annotation,
    PNF, refinement, and demand persistence.
    """

    document_ref = str(entry["document_ref"])
    if resource_ledger is not None:
        resource_ledger.sample(
            "postgres_persistence:before",
            phase="postgres_persistence",
            semantic_counts={"source_bytes": len(source_bytes)},
            details={"document_ref": document_ref},
        )
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
        raise ValueError("operational document identity disagrees with canonical text")
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
        parser_workers=parser_workers,
        parser_limit_chars=parser_limit_chars,
        parser_target_chars=parser_target_chars,
        parser_overlap_chars=parser_overlap_chars,
    )
    calibration_mode = os.environ.get("SENSIBLAW_TRANCHE_CALIBRATION") == "1"
    with store.transaction() as cursor:
        cached_demand_refs = load_completed_operational_build(
            cursor,
            document_ref=document_ref,
            compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
        )
        if cached_demand_refs is not None and not calibration_mode:
            store.persist_occurrence(
                cursor,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                document_ref=document_ref,
                state="reused_compilation",
            )
            if progress is not None and not getattr(progress, "_finished", False):
                progress.advance(
                    amount=DOCUMENT_COMPILE_STAGE_COUNT + 1,
                    message="reused",
                    reused=True,
                    details={
                        "state": "reused_compilation",
                        "build_key_sha256": build_key_sha256,
                    },
                )
                progress.finish(
                    state="completed",
                    details={
                        "state": "reused_compilation",
                        "build_key_sha256": build_key_sha256,
                    },
                )
            return cached_demand_refs

    # Source identity is durable input evidence, not publication.  It must
    # exist before the injected partition strategy can persist FK-backed,
    # reusable execution metadata.
    with store.transaction() as cursor:
        store.persist_source_document(
            cursor,
            document_ref=document_ref,
            media_type=str(entry["media_type"]),
            content_sha256=content_sha256,
            source_bytes=source_bytes,
            canonical_text=canonical_text,
            adapter_ref=media_adapter_ref,
            adapter_version=context.media_normalization_ref,
            compiler_context_ref=context.context_ref,
            normalization_ref=context.media_normalization_ref,
        )

    def persist_partitions(partitions: Sequence[Mapping[str, Any]]) -> None:
        if not hasattr(store, "persist_projection_partitions"):
            return
        with store.transaction() as cursor:
            store.persist_projection_partitions(cursor, partitions=partitions)

    from src.policy.operational_corpus_compilation import (
        compile_document_operational,
    )

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
        parser_workers=parser_workers,
        parser_limit_chars=parser_limit_chars,
        parser_target_chars=parser_target_chars,
        parser_overlap_chars=parser_overlap_chars,
        parser_checkpoint_dir=parser_checkpoint_dir,
        progress=progress,
        projection_partition_persistence=persist_partitions,
        resource_ledger=resource_ledger,
        execution_strategy_ref=execution_strategy_ref,
        database_url=database_url,
        strict_run_ref=strict_run_ref or f"strict:{document_ref}",
    )
    descriptor_artifacts = dict(compilation.artifacts)
    artifacts = dict(descriptor_artifacts)
    manifest_mode = any(_is_manifest_descriptor(value) for value in artifacts.values())
    if manifest_mode and compilation.artifact_reader is None:
        raise ValueError("manifest compilation requires an artifact reader")
    # Production keeps descriptors intact.  Reconstructing them here used to
    # make a second document-wide copy just before persistence.  The explicit
    # materialised policy remains the compatibility route for legacy stores.
    if str(artifacts.get("build_key_sha256") or "") != build_key_sha256:
        raise ValueError("operational compiler build key disagrees with persistence")
    if resource_ledger is not None:
        resource_ledger.sample(
            "postgres_persistence:compiled_artifacts",
            phase="postgres_persistence",
            semantic_counts={
                "artifact_families": len(artifacts),
                "manifest_source_families": sum(
                    1 for value in artifacts.values() if _is_manifest_descriptor(value)
                ),
            },
            details={
                "manifest_mode": any(
                    _is_manifest_descriptor(value) for value in artifacts.values()
                )
            },
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
    refinements = (
        tuple(artifacts.get("factor_refinements") or ()) if not manifest_mode else ()
    )
    candidate_sets = (
        tuple(artifacts.get("binding_candidate_sets") or ())
        if not manifest_mode
        else ()
    )
    factor_anchors = (
        tuple(artifacts.get("factor_anchors") or ()) if not manifest_mode else ()
    )
    candidate_set_builds = (
        tuple(artifacts.get("binding_candidate_set_builds") or ())
        if not manifest_mode
        else ()
    )
    demands = (
        tuple(artifacts.get("resolution_demands") or ()) if not manifest_mode else ()
    )
    meets = (
        _prepare_meets_for_relational_persistence(artifacts.get("typed_meets") or ())
        if not manifest_mode
        else ()
    )
    base_factor_revisions = (
        {
            str(factor["factor_ref"]): factor_revision_ref(factor)
            for factor in tuple((artifacts.get("pnf_graph") or {}).get("factors") or ())
            if isinstance(factor, Mapping)
        }
        if not manifest_mode
        else {}
    )
    resulting_factor_revisions = dict(base_factor_revisions)
    for refinement in refinements:
        resulting = refinement.get("resulting_factor")
        if isinstance(resulting, Mapping):
            resulting_factor_revisions[str(resulting["factor_ref"])] = (
                factor_revision_ref(resulting)
            )
    mentions = tuple(artifacts.get("licensing", {}).get("mentions") or ())
    demand_refs: tuple[str, ...] = ()
    closure_counts: Mapping[str, int | str | bool] = {}
    persistence_guard = ActiveDocumentResourceGuard(document_ref=document_ref)
    reusable_partition_refs = tuple(
        str(row.get("partition_ref"))
        for row in artifacts.get("projection_partition_manifests") or ()
        if isinstance(row, Mapping) and row.get("partition_ref")
    )
    if not manifest_mode:
        _validate_document_parent_closure(
            document_ref=compilation.document_ref,
            relative_path=relative_path,
            execution_phase=execution_phase,
            batch_index=batch_index,
            base_factor_revisions=base_factor_revisions,
            resulting_factor_revisions=resulting_factor_revisions,
            candidate_sets=candidate_sets,
            factor_anchors=factor_anchors,
            refinements=refinements,
            demands=demands,
        )
    persistence_stage = (
        progress.stage(
            "postgres_persistence",
            measures=stage_measure_declaration("postgres_persistence"),
            details={
                "state": "compiled",
                "build_key_sha256": build_key_sha256,
            },
        )
        if progress is not None and hasattr(progress, "stage")
        else nullcontext(None)
    )
    try:
        with persistence_stage as progress_stage:
            with store.savepoint() as cursor:
                persistence_guard.checkpoint(
                    stage="postgres_persistence",
                    current_kernel="postgres_persistence",
                    reusable_partition_refs=reusable_partition_refs,
                )
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
                persist_licensed_spans(
                    cursor,
                    document_ref=compilation.document_ref,
                    mentions=mentions,
                )
                if hasattr(store, "persist_token_batches"):
                    store.persist_token_batches(
                        cursor,
                        document_ref=compilation.document_ref,
                        tokenizer_ref=context.annotation_backend_ref,
                        tokenizer_version=context.compiler_version,
                        token_count=len(canonical_tokens),
                        batches=lambda: _record_batches(canonical_tokens),
                    )
                else:  # pragma: no cover - compatibility test/store seam
                    store.persist_tokens(
                        cursor,
                        document_ref=compilation.document_ref,
                        tokenizer_ref=context.annotation_backend_ref,
                        tokenizer_version=context.compiler_version,
                        tokens=canonical_tokens,
                    )
                annotation_descriptor = descriptor_artifacts.get("annotation_layer")
                if (
                    hasattr(store, "persist_annotation_layer_batches")
                    and isinstance(annotation_descriptor, Mapping)
                    and annotation_descriptor.get("representation") == "manifest"
                    and compilation.artifact_reader is not None
                ):
                    store.persist_annotation_layer_batches(
                        cursor,
                        document_ref=compilation.document_ref,
                        descriptor=annotation_descriptor,
                        reader=compilation.artifact_reader,
                    )
                else:
                    store.persist_annotation_layer(
                        cursor,
                        document_ref=compilation.document_ref,
                        layer=artifacts["annotation_layer"],
                    )
                store.persist_projection_manifests(
                    cursor,
                    partitions=artifacts.get("projection_partition_manifests") or (),
                    manifest=artifacts["document_projection_manifest"],
                )
                if manifest_mode:
                    assert compilation.artifact_reader is not None
                    reader = compilation.artifact_reader
                    pnf_descriptor = artifacts["pnf_graph"]
                    pnf_metadata = _descriptor_metadata(reader, pnf_descriptor)
                    persisted_graph_ref = str(pnf_metadata["graph_ref"])
                    persisted_base_factor_revisions: dict[str, str] = {}
                    closure_validator = ManifestParentClosureValidator()
                    # Factors include their alternatives and residuals, so this
                    # native writer preserves those child rows without a second
                    # factor/alternative/residual collection.
                    for factors in _iter_descriptor_family(
                        reader, pnf_descriptor, "factors"
                    ):
                        closure_validator.admit_factors(factors)
                        persisted_base_factor_revisions.update(
                            persist_pnf_graph(
                                cursor,
                                document_ref=compilation.document_ref,
                                graph={
                                    "graph_ref": pnf_metadata["graph_ref"],
                                    "factors": factors,
                                },
                            )
                        )
                    persisted_resulting_factor_revisions = dict(
                        persisted_base_factor_revisions
                    )
                    refinement_descriptor = artifacts.get("factor_refinements")
                    if _is_manifest_descriptor(refinement_descriptor):
                        for rows in _iter_descriptor_family(
                            reader, refinement_descriptor, "rows"
                        ):
                            closure_validator.admit_refinements(rows)
                            for refinement in rows:
                                resulting = refinement.get("resulting_factor")
                                if isinstance(resulting, Mapping):
                                    persisted_resulting_factor_revisions[
                                        str(resulting["factor_ref"])
                                    ] = persist_factor_revision(
                                        cursor,
                                        document_ref=compilation.document_ref,
                                        factor=resulting,
                                    )
                            persist_resolution_artifacts(
                                cursor,
                                factor_revisions=persisted_resulting_factor_revisions,
                                demands=(),
                                evidence=(),
                                meets=(),
                                refinements=rows,
                            )
                    demand_refs_list: list[str] = []
                    for key, argument in (
                        ("local_evidence", "evidence"),
                        ("typed_meets", "meets"),
                        ("resolution_demands", "demands"),
                    ):
                        descriptor = artifacts.get(key)
                        if not _is_manifest_descriptor(descriptor):
                            continue
                        for rows in _iter_descriptor_family(reader, descriptor, "rows"):
                            if argument == "meets":
                                closure_validator.admit_meets(rows)
                            elif argument == "demands":
                                closure_validator.admit_demands(rows)
                            kwargs: dict[str, Any] = {
                                "demands": (),
                                "evidence": (),
                                "meets": (),
                                "refinements": (),
                            }
                            kwargs[argument] = (
                                _prepare_meets_for_relational_persistence(rows)
                                if argument == "meets"
                                else rows
                            )
                            demand_refs_list.extend(
                                persist_resolution_artifacts(
                                    cursor,
                                    factor_revisions=persisted_resulting_factor_revisions,
                                    **kwargs,
                                )
                            )
                    anchor_descriptor = artifacts.get("factor_anchors")
                    if _is_manifest_descriptor(anchor_descriptor):
                        for rows in _iter_descriptor_family(
                            reader, anchor_descriptor, "rows"
                        ):
                            closure_validator.admit_anchors(rows)
                            persist_binding_candidate_sets(
                                cursor,
                                candidate_sets=(),
                                refinements=(),
                                factor_revisions=persisted_base_factor_revisions,
                                factor_anchors=rows,
                            )
                    set_descriptor = artifacts.get("binding_candidate_sets")
                    if _is_manifest_descriptor(set_descriptor):
                        for rows in _iter_descriptor_family(
                            reader, set_descriptor, "rows"
                        ):
                            closure_validator.admit_candidate_sets(rows)
                            persist_binding_candidate_sets(
                                cursor,
                                candidate_sets=rows,
                                refinements=(),
                                factor_revisions=persisted_base_factor_revisions,
                                validate_indexed_query=True,
                            )
                    build_descriptor = artifacts.get("binding_candidate_set_builds")
                    if _is_manifest_descriptor(build_descriptor):
                        for rows in _iter_descriptor_family(
                            reader, build_descriptor, "rows"
                        ):
                            closure_validator.admit_candidate_builds(rows)
                            _persist_streamed_candidate_builds(cursor, rows)
                    # Candidate sets now exist, so replay only the narrow link
                    # fields from their independently verified source streams.
                    for key, kind in (
                        ("factor_refinements", "refinement"),
                        ("typed_meets", "meet"),
                        ("resolution_demands", "demand"),
                    ):
                        descriptor = artifacts.get(key)
                        if _is_manifest_descriptor(descriptor):
                            for rows in _iter_descriptor_family(
                                reader, descriptor, "rows"
                            ):
                                _persist_streamed_candidate_links(
                                    cursor, kind=kind, rows=rows
                                )
                    closure_receipt = closure_validator.finalize()
                    closure_counts = closure_receipt.to_dict()
                    # A descriptor is a persistence receipt too: consume every
                    # declared stream, including projections not stored in SQL.
                    for value in artifacts.values():
                        if _is_manifest_descriptor(value) and value.get(
                            "artifact_key"
                        ) in {
                            "refined_pnf_graph",
                            "relational_bundle",
                            "semantic_annotation_layer",
                            "canonical_token_rows",
                        }:
                            _verify_descriptor(reader, value)
                    demand_refs = tuple(sorted(set(demand_refs_list)))
                else:
                    persisted_graph_ref = str(artifacts["pnf_graph"]["graph_ref"])
                    persisted_base_factor_revisions = persist_pnf_graph(
                        cursor,
                        document_ref=compilation.document_ref,
                        graph=artifacts["pnf_graph"],
                    )
                    persisted_resulting_factor_revisions = dict(
                        persisted_base_factor_revisions
                    )
                    for refinement in refinements:
                        resulting = refinement.get("resulting_factor")
                        if isinstance(resulting, Mapping):
                            persisted_resulting_factor_revisions[
                                str(resulting["factor_ref"])
                            ] = persist_factor_revision(
                                cursor,
                                document_ref=compilation.document_ref,
                                factor=resulting,
                            )
                    _validate_document_parent_closure(
                        document_ref=compilation.document_ref,
                        relative_path=relative_path,
                        execution_phase=execution_phase,
                        batch_index=batch_index,
                        base_factor_revisions=persisted_base_factor_revisions,
                        resulting_factor_revisions=persisted_resulting_factor_revisions,
                        candidate_sets=candidate_sets,
                        factor_anchors=factor_anchors,
                        refinements=refinements,
                        demands=demands,
                    )
                    demand_refs = persist_resolution_artifacts(
                        cursor,
                        factor_revisions=persisted_resulting_factor_revisions,
                        demands=demands,
                        evidence=artifacts.get("local_evidence") or (),
                        meets=meets,
                        refinements=refinements,
                    )
                    persist_binding_candidate_sets(
                        cursor,
                        candidate_sets=candidate_sets,
                        refinements=refinements,
                        factor_revisions=persisted_base_factor_revisions,
                        factor_anchors=factor_anchors,
                        builds=candidate_set_builds,
                        meets=meets,
                        demands=demands,
                        validate_indexed_query=True,
                    )
                store.persist_artifact_manifests(
                    cursor,
                    document_ref=compilation.document_ref,
                    build_key_sha256=build_key_sha256,
                    descriptors=tuple(
                        value
                        for value in descriptor_artifacts.values()
                        if isinstance(value, Mapping)
                        and value.get("representation") == "manifest"
                    ),
                )
                persistence_guard.checkpoint(
                    stage="postgres_persistence",
                    current_kernel="document_publication",
                    persisted_counts={
                        "factors": len(persisted_base_factor_revisions),
                        "refinements": len(refinements),
                        "demands": len(demand_refs),
                        **closure_counts,
                    },
                    reusable_partition_refs=reusable_partition_refs,
                )
                persist_completed_operational_build(
                    cursor,
                    document_ref=compilation.document_ref,
                    compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
                    build_key_sha256=build_key_sha256,
                    graph_ref=persisted_graph_ref,
                    demand_refs=demand_refs,
                )
                store.persist_occurrence(
                    cursor,
                    corpus_ref=corpus_ref,
                    relative_path=relative_path,
                    document_ref=compilation.document_ref,
                    state="compiled",
                )
                if resource_ledger is not None:
                    resource_ledger.sample(
                        "occurrence_publication:after",
                        phase="postgres_persistence",
                        semantic_counts={
                            "persisted_factors": len(persisted_base_factor_revisions),
                            "persisted_refinements": len(refinements),
                            "persisted_demands": len(demand_refs),
                        },
                    )
                if progress_stage is not None:
                    progress_stage.observe(
                        measures={
                            "rows_written": (
                                1
                                + 1
                                + len(mentions)
                                + len(canonical_tokens)
                                + len(persisted_base_factor_revisions)
                                + len(refinements)
                                + len(demand_refs)
                                + len(candidate_sets)
                                + 1
                            ),
                            "bytes_written": (
                                len(source_bytes) + len(canonical_text.encode("utf-8"))
                            ),
                            "tables_touched": 7,
                            "statements_executed": (
                                1 + 1 + 1 + 1 + len(refinements) + 1 + 1 + 1
                            ),
                            "conflicts_avoided": 0,
                        },
                        details={
                            "state": "compiled",
                            "build_key_sha256": build_key_sha256,
                            "demand_ref_count": len(demand_refs),
                        },
                    )
                result = demand_refs
        if resource_ledger is not None:
            resource_ledger.sample(
                "transaction_commit:after",
                phase="postgres_persistence",
                semantic_counts={"persisted_rows": len(result)},
                details={"publication": "completed_build_and_occurrence"},
                collect_gc=True,
            )
        return result
    except ValueError:
        if progress is not None and not getattr(progress, "_finished", False):
            progress.finish(
                state="failed",
                details={
                    "state": "failed",
                    "build_key_sha256": build_key_sha256,
                },
            )
        raise
    except Exception as error:
        if progress is not None and not getattr(progress, "_finished", False):
            progress.finish(
                state="failed",
                details={
                    "state": "failed",
                    "build_key_sha256": build_key_sha256,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
        first_refinement = refinements[0] if refinements else {}
        prior_factor = (
            first_refinement.get("prior_factor")
            if isinstance(first_refinement, Mapping)
            else None
        )
        raise RuntimeError(
            _parent_closure_violation_message(
                document_ref=compilation.document_ref,
                relative_path=relative_path,
                execution_phase=execution_phase,
                batch_index=batch_index,
                child_table="resolution.refinement",
                child_ref=(
                    str(refinements[0].get("refinement_ref") or "")
                    if refinements
                    else ""
                ),
                parent_table="algebra.factor_revision",
                parent_column="factor_revision_ref",
                missing_parent_ref="unknown",
                semantic_artifact_type="document_persistence",
                producer_contract=_factor_producer_contract(prior_factor)
                if isinstance(prior_factor, Mapping)
                else "unknown",
                detail=f"{type(error).__name__}: {error}",
            )
        ) from error


def compile_directory_postgres(
    input_dir: str | Path,
    *,
    context: CompilerContext,
    store: PostgresCompilerStore,
    recursive: bool = True,
    follow_symlinks: bool = False,
    include_globs: Sequence[str] = (),
    exclude_globs: Sequence[str] = (),
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    execution_phase: str = "local",
    document_executor: CompilationDocumentExecutor = persist_document_compilation,
    document_executor_ref: str = "document-executor:postgres-operational:v0_1",
    document_executor_contract_ref: str = OPERATIONAL_COMPILER_CONTRACT,
    persistence_strategy_ref: str = "persistence:postgres-savepoint:v0_1",
    admission_policy_ref: str = "admission:inventoried-only:v0_1",
    admission_policy: Callable[[Mapping[str, Any]], bool] | None = None,
    closure_workers: int = 1,
    owner_partitions: int = 1,
    parser_workers: int = 2,
    parser_limit_chars: int = 1_000_000,
    parser_target_chars: int = 400_000,
    parser_overlap_chars: int = 8_192,
    document_workers: int = 1,
    worker_budget: int | None = None,
    database_url: str | None = None,
    progress: PhaseRecorder | None = None,
    state_path: str | Path | None = None,
    resume: bool = True,
    resource_ledger: ExecutionResourceLedger | None = None,
    execution_strategy_ref: str = "local-compatibility-replay",
) -> PersistedCompilation:
    """Compile a bounded directory directly into PostgreSQL."""

    # Exact-0008 calibration bypasses completed-build reuse.  Its caller owns
    # one outer transaction and rolls that transaction back after this full
    # path returns; inner savepoints must remain visible to later stages.

    if execution_phase not in {
        "inventory",
        "local",
        "demand_planning",
        "legal_adjunct_demand_planning",
    }:
        raise ValueError("unsupported corpus compilation phase")
    if not execution_strategy_ref:
        raise ValueError("execution_strategy_ref is required")
    if closure_workers < 1:
        raise ValueError("closure_workers must be positive")
    if document_workers < 1:
        raise ValueError("document_workers must be positive")
    if worker_budget is None:
        worker_budget = max(document_workers, closure_workers, parser_workers)
    if worker_budget < 1:
        raise ValueError("worker_budget must be positive")
    scheduled_inner_workers = max(1, worker_budget // document_workers)
    scheduled_closure_workers = min(closure_workers, scheduled_inner_workers)
    scheduled_parser_workers = min(parser_workers, scheduled_inner_workers)
    if owner_partitions < 1:
        raise ValueError("owner_partitions must be positive")
    if not 1 <= parser_workers <= 32:
        raise ValueError("parser_workers must be between 1 and 32")
    root = Path(input_dir).resolve()
    state_file = Path(state_path).resolve() if state_path is not None else None
    run_state: dict[str, Any] | None = None
    if resume:
        run_state = _load_compilation_state(state_file)
    manifest = build_corpus_manifest(
        root,
        context=context,
        recursive=recursive,
        follow_symlinks=follow_symlinks,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if resource_ledger is not None:
        resource_ledger.sample(
            "manifest_replay:after_inventory",
            phase="manifest_replay",
            semantic_counts={
                "manifest_documents": len(manifest.documents),
            },
        )
    manifest_row, prepared_sources = _prepare_operational_manifest(
        root=root,
        manifest=manifest.to_dict(),
        context=context,
    )
    corpus_ref = str(manifest_row["corpus_ref"])
    manifest_sha256 = str(manifest_row["manifest_sha256"])
    if run_state is not None:
        expected_state = {
            "schema_version": COMPILATION_STATE_SCHEMA_VERSION,
            "corpus_ref": corpus_ref,
            "manifest_sha256": manifest_sha256,
            "compiler_context_ref": context.context_ref,
            "execution_phase": execution_phase,
            "document_executor_ref": document_executor_ref,
            "document_executor_contract_ref": document_executor_contract_ref,
            "persistence_strategy_ref": persistence_strategy_ref,
            "admission_policy_ref": admission_policy_ref,
            "parser_workers": parser_workers,
            "parser_limit_chars": parser_limit_chars,
            "parser_target_chars": parser_target_chars,
            "parser_overlap_chars": parser_overlap_chars,
        }
        for key, expected in expected_state.items():
            observed = run_state.get(key)
            if observed is not None and str(observed) != str(expected):
                raise ValueError(
                    f"compilation resume state mismatch for {key}: "
                    f"expected={expected} observed={observed}"
                )
    with store.transaction() as cursor:
        store.persist_context(cursor, context.to_dict())
        store.persist_manifest(cursor, manifest_row)
    if execution_phase == "inventory":
        return PersistedCompilation(corpus_ref, (), (), ())

    compiled: set[str] = set()
    document_refs: list[str] = []
    demand_refs: list[str] = []
    failure_refs: list[str] = []
    resume_documents = (
        dict(run_state.get("documents") or {}) if run_state is not None else {}
    )
    resume_duplicate_occurrences = (
        [
            tuple(row)
            for row in (run_state.get("duplicate_occurrences") or [])
            if isinstance(row, Sequence) and len(row) == 2
        ]
        if run_state is not None
        else []
    )
    ordered_documents = [
        entry
        for entry in manifest_row["ordered_documents"]
        if entry["status"] == "inventoried"
        and (admission_policy(entry) if admission_policy is not None else True)
    ]
    progress_iter = tqdm(
        ordered_documents,
        total=len(ordered_documents),
        desc=f"{execution_phase}_compile",
        unit="doc",
        dynamic_ncols=True,
        leave=True,
        file=sys.stderr,
        disable=not sys.stderr.isatty(),
    )

    class _NoopPhaseHandle:
        def advance(self, **_kwargs: Any) -> None:
            return None

    progress_phase = (
        progress.phase(
            f"postgres_{execution_phase}_compile",
            total=len(ordered_documents),
            worker=document_executor_ref,
            details={
                "document_executor_ref": document_executor_ref,
                "document_executor_contract_ref": document_executor_contract_ref,
                "persistence_strategy_ref": persistence_strategy_ref,
                "admission_policy_ref": admission_policy_ref,
                "closure_workers": closure_workers,
                "owner_partitions": owner_partitions,
                "parser_workers": parser_workers,
                "parser_limit_chars": parser_limit_chars,
                "parser_target_chars": parser_target_chars,
                "parser_overlap_chars": parser_overlap_chars,
                "document_workers": document_workers,
                "worker_budget": worker_budget,
            },
        )
        if progress is not None
        else nullcontext(_NoopPhaseHandle())
    )
    state_row: dict[str, Any] = {
        "schema_version": COMPILATION_STATE_SCHEMA_VERSION,
        "corpus_ref": corpus_ref,
        "manifest_sha256": manifest_sha256,
        "compiler_context_ref": context.context_ref,
        "execution_phase": execution_phase,
        "document_executor_ref": document_executor_ref,
        "document_executor_contract_ref": document_executor_contract_ref,
        "persistence_strategy_ref": persistence_strategy_ref,
        "admission_policy_ref": admission_policy_ref,
        "closure_workers": closure_workers,
        "owner_partitions": owner_partitions,
        "parser_workers": parser_workers,
        "parser_limit_chars": parser_limit_chars,
        "parser_target_chars": parser_target_chars,
        "parser_overlap_chars": parser_overlap_chars,
        "document_workers": document_workers,
        "worker_budget": worker_budget,
        "root": str(root),
        "documents": resume_documents,
        "duplicate_occurrences": resume_duplicate_occurrences,
        "document_refs": [],
        "demand_refs": [],
        "failure_refs": [],
        "completed_document_count": 0,
    }
    compiled.update(
        {
            document_ref
            for document_ref, payload in resume_documents.items()
            if isinstance(payload, Mapping)
            and str(payload.get("state") or "")
            in {
                "compiled",
                "reused_compilation",
            }
            and str(payload.get("build_key_sha256") or "")
        }
    )
    if resume_documents:
        for payload in resume_documents.values():
            if not isinstance(payload, Mapping):
                continue
            if str(payload.get("state") or "") not in {
                "compiled",
                "reused_compilation",
            }:
                continue
            document_ref = str(payload.get("document_ref") or "")
            if document_ref:
                document_refs.append(document_ref)
                demand_refs.extend(str(ref) for ref in payload.get("demand_refs") or ())
                if payload.get("failure_ref"):
                    failure_refs.append(str(payload["failure_ref"]))
    state_row["document_refs"] = list(document_refs)
    state_row["demand_refs"] = list(demand_refs)
    state_row["failure_refs"] = list(failure_refs)
    state_row["completed_document_count"] = len(document_refs)
    with progress_phase as phase_handle:
        if phase_handle is None:
            phase_handle = _NoopPhaseHandle()
        if document_workers > 1:
            if database_url is None:
                try:
                    database_url = str(store.connection.info.dsn)
                except AttributeError as error:
                    raise ValueError(
                        "database_url is required for document_workers > 1"
                    ) from error
            futures: dict[Future[dict[str, Any]], tuple[str, str, str]] = {}
            with ProcessPoolExecutor(
                max_workers=document_workers,
            ) as executor:
                for batch_index, entry in enumerate(progress_iter, start=1):
                    document_ref = str(entry["document_ref"])
                    relative_path = str(entry["relative_path"])
                    worker_ref = f"{document_executor_ref}:doc-{batch_index:04d}"
                    if document_ref in compiled:
                        phase_handle.advance(
                            subject_ref=document_ref,
                            message="reused",
                            reused=True,
                            details={
                                "relative_path": relative_path,
                                "worker": worker_ref,
                            },
                            worker=worker_ref,
                        )
                        continue
                    prepared = prepared_sources.get(relative_path)
                    if prepared is None:
                        source_bytes = (root / relative_path).read_bytes()
                        source_text = source_bytes.decode("utf-8")
                    else:
                        source_bytes, source_text = prepared
                    canonical_text, canonical_text_sha256, media_adapter_ref = (
                        _canonical_source_coordinates(
                            media_type=str(entry["media_type"]),
                            source_text=source_text,
                            source_ref=f"document-source:{document_ref}",
                        )
                    )
                    build_key_sha256 = _operational_build_key(
                        document_ref=document_ref,
                        content_sha256=str(entry["content_sha256"]),
                        canonical_text_sha256=canonical_text_sha256,
                        media_adapter_ref=media_adapter_ref,
                        context=context,
                        parser_workers=scheduled_parser_workers,
                        parser_limit_chars=parser_limit_chars,
                        parser_target_chars=parser_target_chars,
                        parser_overlap_chars=parser_overlap_chars,
                    )
                    parser_checkpoint_dir = (
                        str(
                            state_file.parent
                            / f"{state_file.stem}_chunks"
                            / document_ref.removeprefix("document:")
                        )
                        if state_file is not None
                        else None
                    )
                    payload = {
                        "document_ref": document_ref,
                        "relative_path": relative_path,
                        "worker_ref": worker_ref,
                        "entry": entry,
                        "source_bytes": source_bytes,
                        "source_text": canonical_text,
                        "context": context,
                        "execution_phase": execution_phase,
                        "batch_index": batch_index,
                        "corpus_ref": corpus_ref,
                        "build_key_sha256": build_key_sha256,
                        "document_executor": document_executor,
                        "document_executor_contract_ref": document_executor_contract_ref,
                        "closure_workers": scheduled_closure_workers,
                        "owner_partitions": owner_partitions,
                        "parser_workers": scheduled_parser_workers,
                        "parser_limit_chars": parser_limit_chars,
                        "parser_target_chars": parser_target_chars,
                        "parser_overlap_chars": parser_overlap_chars,
                        "parser_checkpoint_dir": parser_checkpoint_dir,
                        "execution_strategy_ref": execution_strategy_ref,
                        "strict_run_ref": f"strict:{document_ref}",
                    }
                    future = executor.submit(
                        _compile_document_postgres_worker,
                        database_url=database_url,
                        progress=progress is not None,
                        store_kwargs=payload,
                    )
                    futures[future] = (document_ref, relative_path, worker_ref)
                for future in as_completed(futures):
                    document_ref, relative_path, worker_ref = futures[future]
                    result = future.result()
                    state = str(result["state"])
                    if state in {"compiled", "reused_compilation"}:
                        compiled.add(document_ref)
                        document_refs.append(document_ref)
                        demand_refs.extend(
                            str(ref) for ref in result.get("demand_refs") or ()
                        )
                    if result.get("failure_ref"):
                        failure_refs.append(str(result["failure_ref"]))
                    resume_documents[document_ref] = result
                    state_row.update(
                        document_refs=list(document_refs),
                        demand_refs=list(demand_refs),
                        failure_refs=list(failure_refs),
                        completed_document_count=len(document_refs),
                    )
                    _save_compilation_state(state_file, state_row)
                    phase_handle.advance(
                        subject_ref=document_ref,
                        message=state,
                        reused=state == "reused_compilation",
                        details={
                            "relative_path": relative_path,
                            "worker": worker_ref,
                            **result,
                        },
                        worker=worker_ref,
                    )
            if sys.stderr.isatty():
                progress_iter.close()
            state_row.update(
                document_refs=list(document_refs),
                demand_refs=list(demand_refs),
                failure_refs=list(failure_refs),
                completed_document_count=len(document_refs),
            )
            _save_compilation_state(state_file, state_row)
            return PersistedCompilation(
                corpus_ref=corpus_ref,
                document_refs=tuple(sorted(document_refs)),
                demand_refs=tuple(sorted(set(demand_refs))),
                failure_refs=tuple(sorted(failure_refs)),
            )
        for batch_index, entry in enumerate(progress_iter, start=1):
            document_ref = str(entry["document_ref"])
            relative_path = str(entry["relative_path"])
            worker_ref = f"{document_executor_ref}:doc-{batch_index:04d}"
            if document_ref in compiled:
                if sys.stderr.isatty():
                    progress_iter.set_postfix_str("reused", refresh=False)
                phase_handle.advance(
                    subject_ref=document_ref,
                    message="reused",
                    reused=True,
                    details={
                        "relative_path": relative_path,
                        "worker": worker_ref,
                        "state": "reused_checkpoint",
                    },
                    worker=worker_ref,
                )
                continue
            try:
                prepared = prepared_sources.get(relative_path)
                if prepared is None:
                    source_bytes = (root / relative_path).read_bytes()
                    source_text = source_bytes.decode("utf-8")
                else:
                    source_bytes, source_text = prepared
                canonical_text, canonical_text_sha256, media_adapter_ref = (
                    _canonical_source_coordinates(
                        media_type=str(entry["media_type"]),
                        source_text=source_text,
                        source_ref=f"document-source:{document_ref}",
                    )
                )
                build_key_sha256 = _operational_build_key(
                    document_ref=document_ref,
                    content_sha256=str(entry["content_sha256"]),
                    canonical_text_sha256=canonical_text_sha256,
                    media_adapter_ref=media_adapter_ref,
                    context=context,
                    parser_workers=scheduled_parser_workers,
                    parser_limit_chars=parser_limit_chars,
                    parser_target_chars=parser_target_chars,
                    parser_overlap_chars=parser_overlap_chars,
                )
                state_entry = resume_documents.get(document_ref)
                if (
                    isinstance(state_entry, Mapping)
                    and os.environ.get("SENSIBLAW_TRANCHE_CALIBRATION") != "1"
                    and str(state_entry.get("build_key_sha256") or "")
                    == build_key_sha256
                    and str(state_entry.get("state") or "")
                    in {
                        "compiled",
                        "reused_compilation",
                    }
                ):
                    refs = tuple(
                        str(ref) for ref in state_entry.get("demand_refs") or ()
                    )
                    compiled.add(document_ref)
                    document_refs.append(document_ref)
                    demand_refs.extend(refs)
                    if sys.stderr.isatty():
                        progress_iter.set_postfix_str("reused", refresh=False)
                    phase_handle.advance(
                        subject_ref=document_ref,
                        message="reused",
                        reused=True,
                        details={
                            "relative_path": relative_path,
                            "worker": str(state_entry.get("worker") or worker_ref),
                            "state": str(
                                state_entry.get("state") or "reused_compilation"
                            ),
                            "build_key_sha256": build_key_sha256,
                            "closure_workers": closure_workers,
                            "owner_partitions": owner_partitions,
                        },
                        worker=str(state_entry.get("worker") or worker_ref),
                    )
                    continue
                with store.transaction() as cursor:
                    cached_demand_refs = load_completed_operational_build(
                        cursor,
                        document_ref=document_ref,
                        compiler_contract_ref=document_executor_contract_ref,
                        build_key_sha256=build_key_sha256,
                    )
                if (
                    cached_demand_refs is not None
                    and os.environ.get("SENSIBLAW_TRANCHE_CALIBRATION") != "1"
                ):
                    with store.transaction() as cursor:
                        store.persist_occurrence(
                            cursor,
                            corpus_ref=corpus_ref,
                            relative_path=relative_path,
                            document_ref=document_ref,
                            state="reused_compilation",
                        )
                    compiled.add(document_ref)
                    document_refs.append(document_ref)
                    demand_refs.extend(cached_demand_refs)
                    resume_documents[document_ref] = {
                        "document_ref": document_ref,
                        "relative_path": relative_path,
                        "state": "reused_compilation",
                        "build_key_sha256": build_key_sha256,
                        "demand_refs": list(cached_demand_refs),
                        "worker": worker_ref,
                    }
                    _save_compilation_state(state_file, state_row)
                    if sys.stderr.isatty():
                        progress_iter.set_postfix_str("reused", refresh=False)
                    phase_handle.advance(
                        subject_ref=document_ref,
                        message="reused",
                        reused=True,
                        details={
                            "relative_path": relative_path,
                            "worker": worker_ref,
                            "state": "reused_compilation",
                            "build_key_sha256": build_key_sha256,
                            "closure_workers": closure_workers,
                            "owner_partitions": owner_partitions,
                        },
                        worker=worker_ref,
                    )
                    continue
                started_ns = monotonic_ns()
                if hasattr(phase_handle, "heartbeat"):
                    phase_handle.heartbeat(
                        subject_ref=relative_path,
                        message="active document",
                        details={
                            "document_ref": document_ref,
                            "relative_path": relative_path,
                            "worker": worker_ref,
                            "state": "running",
                        },
                        worker=worker_ref,
                    )
                document_guard = ActiveDocumentResourceGuard(
                    document_ref=document_ref
                )
                with (
                    progress.phase(
                        f"postgres_{execution_phase}_document_compile",
                        total=DOCUMENT_COMPILE_STAGE_COUNT + 1,
                        subject_ref=relative_path,
                        message="document compile",
                        worker=worker_ref,
                        details={
                            "document_ref": document_ref,
                            "relative_path": relative_path,
                            "build_key_sha256": build_key_sha256,
                            "execution_phase": execution_phase,
                        },
                        heartbeat_seconds=30.0,
                    )
                    if progress is not None
                    else nullcontext(None)
                ) as document_progress:
                    guarded_document_progress = (
                        GuardedDocumentProgress(document_progress, document_guard)
                        if document_progress is not None
                        else None
                    )
                    executor_kwargs: dict[str, Any] = {
                        "store": store,
                        "corpus_ref": corpus_ref,
                        "relative_path": relative_path,
                        "entry": entry,
                        "source_bytes": source_bytes,
                        "source_text": source_text,
                        "context": context,
                        "execution_phase": execution_phase,
                        "batch_index": batch_index,
                        "closure_workers": scheduled_closure_workers,
                        "owner_partitions": owner_partitions,
                        "parser_workers": scheduled_parser_workers,
                        "parser_limit_chars": parser_limit_chars,
                        "parser_target_chars": parser_target_chars,
                        "parser_overlap_chars": parser_overlap_chars,
                        "parser_checkpoint_dir": (
                            str(
                                state_file.parent
                                / f"{state_file.stem}_chunks"
                                / document_ref.removeprefix("document:")
                            )
                            if state_file is not None
                            else None
                        ),
                        "progress": guarded_document_progress,
                        "execution_strategy_ref": execution_strategy_ref,
                        "database_url": database_url,
                        "strict_run_ref": f"strict:{document_ref}",
                    }
                    if resource_ledger is not None and (
                        "resource_ledger"
                        in inspect.signature(document_executor).parameters
                        or any(
                            parameter.kind is inspect.Parameter.VAR_KEYWORD
                            for parameter in inspect.signature(
                                document_executor
                            ).parameters.values()
                        )
                    ):
                        executor_kwargs["resource_ledger"] = resource_ledger
                    refs = document_executor(**executor_kwargs)
            except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
                if (
                    execution_strategy_ref == "postgresql-leased-exact-execution:v1"
                    and isinstance(error, StrictExecutionError)
                ):
                    raise
                with store.transaction() as cursor:
                    failure_ref = store.persist_failure(
                        cursor,
                        target_ref=document_ref,
                        phase_ref="local_compile",
                        error=error,
                    )
                failure_refs.append(failure_ref)
                resume_documents[document_ref] = {
                    "document_ref": document_ref,
                    "relative_path": relative_path,
                    "state": "failed",
                    "failure_ref": failure_ref,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "worker": worker_ref,
                }
                state_row["document_refs"] = list(document_refs)
                state_row["demand_refs"] = list(demand_refs)
                state_row["failure_refs"] = list(failure_refs)
                state_row["completed_document_count"] = len(document_refs)
                _save_compilation_state(state_file, state_row)
                if sys.stderr.isatty():
                    progress_iter.set_postfix_str("failed", refresh=False)
                phase_handle.advance(
                    subject_ref=document_ref,
                    message="failed",
                    reused=False,
                    details={
                        "relative_path": relative_path,
                        "worker": worker_ref,
                        "state": "failed",
                        "error_type": type(error).__name__,
                        "error": str(error),
                    },
                    worker=worker_ref,
                )
                continue
            compiled.add(document_ref)
            document_refs.append(document_ref)
            demand_refs.extend(refs)
            resume_documents[document_ref] = {
                "document_ref": document_ref,
                "relative_path": relative_path,
                "state": "compiled",
                "build_key_sha256": build_key_sha256,
                "demand_refs": list(refs),
                "worker": worker_ref,
                "elapsed_ms": max(0, (monotonic_ns() - started_ns) // 1_000_000),
            }
            state_row["document_refs"] = list(document_refs)
            state_row["demand_refs"] = list(demand_refs)
            state_row["failure_refs"] = list(failure_refs)
            state_row["completed_document_count"] = len(document_refs)
            _save_compilation_state(state_file, state_row)
            if sys.stderr.isatty():
                progress_iter.set_postfix_str("ok", refresh=False)
            phase_handle.advance(
                subject_ref=document_ref,
                message="compiled",
                reused=False,
                details={
                    "relative_path": relative_path,
                    "worker": worker_ref,
                    "state": "compiled",
                    "build_key_sha256": build_key_sha256,
                    "closure_workers": closure_workers,
                    "owner_partitions": owner_partitions,
                },
                worker=worker_ref,
            )
    if sys.stderr.isatty():
        progress_iter.close()
    state_row["document_refs"] = list(document_refs)
    state_row["demand_refs"] = list(demand_refs)
    state_row["failure_refs"] = list(failure_refs)
    state_row["completed_document_count"] = len(document_refs)
    _save_compilation_state(state_file, state_row)
    return PersistedCompilation(
        corpus_ref=corpus_ref,
        document_refs=tuple(sorted(document_refs)),
        demand_refs=tuple(sorted(set(demand_refs))),
        failure_refs=tuple(sorted(failure_refs)),
    )


__all__ = ["compile_directory_postgres", "persist_document_compilation"]


def __getattr__(name: str) -> Any:
    if name == "compile_document_operational":
        from src.policy.operational_corpus_compilation import (
            compile_document_operational,
        )

        return compile_document_operational
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
