"""PostgreSQL-backed corpus compilation with no semantic JSON projections."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.ingestion.media_adapter import HtmlDocumentMediaAdapter
from src.policy.carriers.canonical import canonical_sha256
from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    compile_document_operational,
)
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


def persist_document_compilation(
    *,
    store: PostgresCompilerStore,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    source_text: str,
    context: CompilerContext,
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
                factor_ref = str(resulting["factor_ref"])
                resulting_factor_revisions[factor_ref] = revision_ref
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
        persist_completed_operational_build(
            cursor,
            document_ref=compilation.document_ref,
            compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
            build_key_sha256=build_key_sha256,
            graph_ref=str(artifacts["pnf_graph"]["graph_ref"]),
            demand_refs=demand_refs,
        )
        return demand_refs


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
) -> PersistedCompilation:
    """Compile a bounded directory directly into PostgreSQL."""

    if execution_phase not in {"inventory", "local", "demand_planning"}:
        raise ValueError("unsupported corpus compilation phase")
    root = Path(input_dir).resolve()
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
    with store.transaction() as cursor:
        store.persist_context(cursor, context.to_dict())
        store.persist_manifest(cursor, manifest_row)
    if execution_phase == "inventory":
        return PersistedCompilation(corpus_ref, (), (), ())

    compiled: set[str] = set()
    document_refs: list[str] = []
    demand_refs: list[str] = []
    failure_refs: list[str] = []
    for entry in manifest_row["ordered_documents"]:
        if entry["status"] != "inventoried":
            continue
        document_ref = str(entry["document_ref"])
        relative_path = str(entry["relative_path"])
        if document_ref in compiled:
            with store.transaction() as cursor:
                store.persist_occurrence(
                    cursor,
                    corpus_ref=corpus_ref,
                    relative_path=relative_path,
                    document_ref=document_ref,
                    state="duplicate_content_occurrence",
                )
            continue
        try:
            prepared = prepared_sources.get(relative_path)
            if prepared is None:
                source_bytes = (root / relative_path).read_bytes()
                source_text = source_bytes.decode("utf-8")
            else:
                source_bytes, source_text = prepared
            refs = persist_document_compilation(
                store=store,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                entry=entry,
                source_bytes=source_bytes,
                source_text=source_text,
                context=context,
            )
        except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
            with store.transaction() as cursor:
                failure_refs.append(
                    store.persist_failure(
                        cursor,
                        target_ref=document_ref,
                        phase_ref="local_compile",
                        error=error,
                    )
                )
            continue
        compiled.add(document_ref)
        document_refs.append(document_ref)
        demand_refs.extend(refs)
    return PersistedCompilation(
        corpus_ref=corpus_ref,
        document_refs=tuple(sorted(document_refs)),
        demand_refs=tuple(sorted(set(demand_refs))),
        failure_refs=tuple(sorted(failure_refs)),
    )


__all__ = ["compile_directory_postgres", "persist_document_compilation"]
