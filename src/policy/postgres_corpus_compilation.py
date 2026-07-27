"""PostgreSQL-backed corpus compilation with no semantic JSON projections."""

from __future__ import annotations

from contextlib import nullcontext
import json
import hashlib
import os
import sys
from pathlib import Path
import tempfile
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from tqdm.auto import tqdm

from src.ingestion.media_adapter import HtmlDocumentMediaAdapter
from src.policy.carriers.canonical import canonical_sha256
from src.policy.algebra.revision_identity import factor_revision_ref
from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    DOCUMENT_COMPILE_STAGE_COUNT,
    compile_document_operational,
)
from src.runtime.progress import PhaseRecorder
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


def _canonical_source_coordinates(
    *, media_type: str, source_text: str, source_ref: str
) -> tuple[str, str, str]:
    """Return the deterministic text coordinate system used by the compiler."""

    if media_type == "text/html":
        canonical_text = HtmlDocumentMediaAdapter(
            source_artifact_ref=source_ref
        ).adapt(source_text).text
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
) -> str:
    return canonical_sha256(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "canonical_text_sha256": canonical_text_sha256,
            "media_adapter_ref": media_adapter_ref,
            "context": context.to_dict(),
            "compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
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
        raise ValueError("operational compiler canonical text disagrees with persistence")
    canonical_text_sha256 = str(artifacts.get("canonical_text_sha256") or "")
    if canonical_text_sha256 != expected_sha256:
        raise ValueError("operational compiler canonical text hash disagrees with persistence")
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
                    missing_parent_ref=str(
                        demand.get("factor_revision_ref") or ""
                    ),
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
    progress: Any | None = None,
) -> tuple[str, ...]:
    """Compile and persist one document transactionally.

    Raw source bytes remain source evidence. The compiler-produced canonical
    projection is the only coordinate system used by token, span, annotation,
    PNF, refinement, and demand persistence.
    """

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

    compilation = compile_document_operational(
        {
            "document_ref": document_ref,
            "content_sha256": content_sha256,
            "media_type": entry["media_type"],
            "canonical_text": source_text,
            "source_ref": source_ref,
        },
        context,
        progress=progress,
    )
    artifacts = compilation.artifacts
    if str(artifacts.get("build_key_sha256") or "") != build_key_sha256:
        raise ValueError("operational compiler build key disagrees with persistence")
    source_normalisation = artifacts.get("source_normalisation") or {}
    if str(source_normalisation.get("adapter_ref") or "") != media_adapter_ref:
        raise ValueError("operational compiler media adapter disagrees with persistence")
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
    base_factor_revisions = {
        str(factor["factor_ref"]): factor_revision_ref(factor)
        for factor in tuple((artifacts.get("pnf_graph") or {}).get("factors") or ())
        if isinstance(factor, Mapping)
    }
    resulting_factor_revisions = dict(base_factor_revisions)
    for refinement in refinements:
        resulting = refinement.get("resulting_factor")
        if isinstance(resulting, Mapping):
            resulting_factor_revisions[str(resulting["factor_ref"])] = (
                factor_revision_ref(resulting)
            )
    demand_refs: tuple[str, ...] = ()
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
    try:
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
                    revision_ref = persist_factor_revision(
                        cursor,
                        document_ref=compilation.document_ref,
                        factor=resulting,
                    )
                    factor_ref = str(resulting["factor_ref"])
                    persisted_resulting_factor_revisions[factor_ref] = revision_ref
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
            persist_completed_operational_build(
                cursor,
                document_ref=compilation.document_ref,
                compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
                build_key_sha256=build_key_sha256,
                graph_ref=str(artifacts["pnf_graph"]["graph_ref"]),
                demand_refs=demand_refs,
            )
            if progress is not None and not getattr(progress, "_finished", False):
                progress.advance(
                    message="persistence",
                    details={
                        "state": "compiled",
                        "build_key_sha256": build_key_sha256,
                        "demand_ref_count": len(demand_refs),
                    },
                )
                progress.finish(
                    state="completed",
                    details={
                        "state": "compiled",
                        "build_key_sha256": build_key_sha256,
                    },
                )
            return demand_refs
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
    progress: PhaseRecorder | None = None,
    state_path: str | Path | None = None,
    resume: bool = True,
) -> PersistedCompilation:
    """Compile a bounded directory directly into PostgreSQL."""

    if execution_phase not in {"inventory", "local", "demand_planning"}:
        raise ValueError("unsupported corpus compilation phase")
    if closure_workers < 1:
        raise ValueError("closure_workers must be positive")
    if owner_partitions < 1:
        raise ValueError("owner_partitions must be positive")
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
    resume_duplicate_occurrences = [
        tuple(row)
        for row in (run_state.get("duplicate_occurrences") or [])
        if isinstance(row, Sequence) and len(row) == 2
    ] if run_state is not None else []
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
            and str(payload.get("state") or "") in {
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
                )
                state_entry = resume_documents.get(document_ref)
                if (
                    isinstance(state_entry, Mapping)
                    and str(state_entry.get("build_key_sha256") or "")
                    == build_key_sha256
                    and str(state_entry.get("state") or "") in {
                        "compiled",
                        "reused_compilation",
                    }
                ):
                    refs = tuple(str(ref) for ref in state_entry.get("demand_refs") or ())
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
                            "state": str(state_entry.get("state") or "reused_compilation"),
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
                if cached_demand_refs is not None:
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
                    refs = document_executor(
                        store=store,
                        corpus_ref=corpus_ref,
                        relative_path=relative_path,
                        entry=entry,
                        source_bytes=source_bytes,
                        source_text=source_text,
                        context=context,
                        execution_phase=execution_phase,
                        batch_index=batch_index,
                        closure_workers=closure_workers,
                        owner_partitions=owner_partitions,
                        progress=document_progress,
                )
            except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
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
