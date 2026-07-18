"""PostgreSQL-backed corpus compilation with no semantic JSON projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.pnf.binding_candidate_sets import compact_binding_artifacts
from src.policy.corpus_compilation import (
    CompilerContext,
    build_corpus_manifest,
    compile_document,
)
from src.sensiblaw.interfaces.shared_reducer import tokenize_canonical_with_spans
from src.storage.postgres import PersistedCompilation, PostgresCompilerStore
from src.storage.postgres.binding_candidate_store import persist_binding_candidate_sets
from src.storage.postgres.factor_revision_store import persist_factor_revision
from src.storage.postgres.semantic_store import (
    persist_pnf_graph,
    persist_resolution_artifacts,
)
from src.storage.postgres.span_store import persist_licensed_spans


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


def persist_document_compilation(
    *,
    store: PostgresCompilerStore,
    corpus_ref: str,
    relative_path: str,
    entry: Mapping[str, Any],
    source_bytes: bytes,
    canonical_text: str,
    context: CompilerContext,
) -> tuple[str, ...]:
    """Compile and persist one document transactionally.

    The operational representation constructs candidate sets directly from the
    preserved annotation graph and factor index. Pairwise binding evidence is
    discarded before persistence and survives only in explicit compatibility
    exports. Candidate sets never close identity, occurrence, truth, or
    expletive status.
    """

    compilation = compile_document(
        {
            "document_ref": entry["document_ref"],
            "content_sha256": entry["content_sha256"],
            "media_type": entry["media_type"],
            "canonical_text": canonical_text,
            "source_ref": f"document-source:{entry['document_ref']}",
        },
        context,
    )
    artifacts = compact_binding_artifacts(compilation.artifacts)
    refinements = tuple(artifacts.get("factor_refinements") or ())
    candidate_sets = tuple(artifacts.get("binding_candidate_sets") or ())
    factor_anchors = tuple(artifacts.get("factor_anchors") or ())
    candidate_set_builds = tuple(
        artifacts.get("binding_candidate_set_builds") or ()
    )
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
            adapter_ref=str(entry["adapter_capability_ref"]),
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
            tokens=tokenize_canonical_with_spans(canonical_text),
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
            demands=artifacts.get("resolution_demands") or (),
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
            validate_indexed_query=True,
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
    manifest_row = manifest.to_dict()
    with store.transaction() as cursor:
        store.persist_context(cursor, context.to_dict())
        store.persist_manifest(cursor, manifest_row)
    if execution_phase == "inventory":
        return PersistedCompilation(manifest.corpus_ref, (), (), ())

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
                    corpus_ref=manifest.corpus_ref,
                    relative_path=relative_path,
                    document_ref=document_ref,
                    state="duplicate_content_occurrence",
                )
            continue
        try:
            source_bytes = (root / relative_path).read_bytes()
            canonical_text = source_bytes.decode("utf-8")
            refs = persist_document_compilation(
                store=store,
                corpus_ref=manifest.corpus_ref,
                relative_path=relative_path,
                entry=entry,
                source_bytes=source_bytes,
                canonical_text=canonical_text,
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
        corpus_ref=manifest.corpus_ref,
        document_refs=tuple(sorted(document_refs)),
        demand_refs=tuple(sorted(set(demand_refs))),
        failure_refs=tuple(sorted(failure_refs)),
    )


__all__ = ["compile_directory_postgres", "persist_document_compilation"]
