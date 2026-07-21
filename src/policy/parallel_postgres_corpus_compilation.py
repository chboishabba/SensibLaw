"""Bounded document-level PostgreSQL compilation with deterministic reduction.

Corpus admission and the final result ordering remain serialized. Each worker owns a
short-lived PostgreSQL connection and compiles exactly one immutable document build.
No worker mutates a shared graph object or a mutable corpus pointer.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.sensiblaw.interfaces import tokenize_canonical_with_spans
from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.operational_corpus_compilation import OPERATIONAL_COMPILER_CONTRACT
from src.policy.postgres_corpus_compilation import (
    _operational_build_key,
    _prepare_operational_manifest,
    persist_document_compilation,
)
from src.runtime.progress import PhaseHandle
from src.storage.postgres import PersistedCompilation, PostgresCompilerStore
from src.storage.postgres.operational_build_store import load_completed_operational_build


PARALLEL_COMPILATION_SCHEMA_VERSION = "sl.parallel_postgres_compilation.v0_1"


@dataclass(frozen=True)
class DocumentCompilationOutcome:
    document_ref: str
    relative_path: str
    state: str
    demand_refs: tuple[str, ...] = ()
    failure_ref: str | None = None
    elapsed_ms: int = 0
    canonical_token_count: int = 0
    worker: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PARALLEL_COMPILATION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "relative_path": self.relative_path,
            "state": self.state,
            "demand_refs": list(self.demand_refs),
            "failure_ref": self.failure_ref,
            "elapsed_ms": self.elapsed_ms,
            "canonical_token_count": self.canonical_token_count,
            "worker": self.worker,
        }


def _build_key(entry: Mapping[str, Any], context: CompilerContext) -> str:
    return _operational_build_key(
        document_ref=str(entry["document_ref"]),
        content_sha256=str(entry["content_sha256"]),
        canonical_text_sha256=str(entry["canonical_text_sha256"]),
        media_adapter_ref=str(entry["media_adapter_ref"]),
        context=context,
    )


def _compile_one(
    *,
    database_url: str,
    corpus_ref: str,
    root: Path,
    entry: Mapping[str, Any],
    prepared_source: tuple[bytes, str] | None,
    context: CompilerContext,
    worker: str,
) -> DocumentCompilationOutcome:
    started = monotonic_ns()
    document_ref = str(entry["document_ref"])
    relative_path = str(entry["relative_path"])
    store = PostgresCompilerStore.connect(database_url)
    try:
        build_key = _build_key(entry, context)
        with store.transaction() as cursor:
            cached = load_completed_operational_build(
                cursor,
                document_ref=document_ref,
                compiler_contract_ref=OPERATIONAL_COMPILER_CONTRACT,
                build_key_sha256=build_key,
            )
        if prepared_source is None:
            source_bytes = (root / relative_path).read_bytes()
            source_text = source_bytes.decode("utf-8")
        else:
            source_bytes, source_text = prepared_source
        demand_refs = persist_document_compilation(
            store=store,
            corpus_ref=corpus_ref,
            relative_path=relative_path,
            entry=entry,
            source_bytes=source_bytes,
            source_text=source_text,
            context=context,
        )
        with store.transaction() as cursor:
            canonical_token_count = store.count_persisted_tokens(
                cursor,
                document_ref=document_ref,
            )
        return DocumentCompilationOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="reused" if cached is not None else "compiled",
            demand_refs=tuple(sorted(set(demand_refs))),
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            canonical_token_count=canonical_token_count,
            worker=worker,
        )
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
        with store.transaction() as cursor:
            failure_ref = store.persist_failure(
                cursor,
                target_ref=document_ref,
                phase_ref="local_compile",
                error=error,
            )
        return DocumentCompilationOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="failed",
            failure_ref=failure_ref,
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            worker=worker,
        )
    finally:
        store.close()


def compile_directory_postgres_parallel(
    input_dir: str | Path,
    *,
    context: CompilerContext,
    database_url: str,
    workers: int = 2,
    recursive: bool = True,
    follow_symlinks: bool = False,
    include_globs: Sequence[str] = (),
    exclude_globs: Sequence[str] = (),
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    execution_phase: str = "local",
    progress: PhaseHandle | None = None,
    outcome_sink: Callable[[DocumentCompilationOutcome], None] | None = None,
) -> tuple[PersistedCompilation, tuple[DocumentCompilationOutcome, ...]]:
    """Compile distinct canonical documents concurrently and reduce stably.

    Duplicate-content occurrences are admitted serially. Workers use independent
    database connections. Returned document, demand, failure, and timing rows are
    sorted by stable references rather than completion order.
    """

    phases = {"inventory", "local", "demand_planning", "legal_catalogue_build"}
    if execution_phase not in phases:
        raise ValueError("unsupported corpus compilation phase")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")

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
    admission_store = PostgresCompilerStore.connect(database_url)
    try:
        with admission_store.transaction() as cursor:
            admission_store.persist_context(cursor, context.to_dict())
            admission_store.persist_manifest(cursor, manifest_row)
        if execution_phase == "inventory":
            empty = PersistedCompilation(corpus_ref, (), (), ())
            return empty, ()

        admitted: list[Mapping[str, Any]] = []
        duplicate_occurrences: list[tuple[str, str]] = []
        seen: set[str] = set()
        for entry in manifest_row["ordered_documents"]:
            if entry["status"] != "inventoried":
                continue
            document_ref = str(entry["document_ref"])
            relative_path = str(entry["relative_path"])
            if document_ref in seen:
                duplicate_occurrences.append((document_ref, relative_path))
                continue
            seen.add(document_ref)
            admitted.append(entry)
    finally:
        admission_store.close()

    if progress is not None:
        progress.total = len(admitted)
        progress.total_tokens = sum(
            len(tokenize_canonical_with_spans(prepared_sources[str(entry["relative_path"])][1]))
            for entry in admitted
        )

    outcomes: list[DocumentCompilationOutcome] = []
    with ProcessPoolExecutor(
        max_workers=workers,
    ) as executor:
        future_map: dict[Future[DocumentCompilationOutcome], str] = {}
        for index, entry in enumerate(admitted):
            relative_path = str(entry["relative_path"])
            worker = f"document-{(index % workers) + 1}"
            future = executor.submit(
                _compile_one,
                database_url=database_url,
                corpus_ref=corpus_ref,
                root=root,
                entry=entry,
                prepared_source=prepared_sources.get(relative_path),
                context=context,
                worker=worker,
            )
            future_map[future] = str(entry["document_ref"])

        for future in as_completed(future_map):
            outcome = future.result()
            outcomes.append(outcome)
            if outcome_sink is not None:
                outcome_sink(outcome)
            if progress is not None:
                progress.advance(
                    subject_ref=outcome.document_ref,
                    message=outcome.state,
                    reused=outcome.state == "reused",
                    details={
                        "elapsed_ms": outcome.elapsed_ms,
                        "worker": outcome.worker,
                        "relative_path": outcome.relative_path,
                        "failure_ref": outcome.failure_ref,
                        "canonical_token_count": outcome.canonical_token_count,
                    },
                    processed_tokens=outcome.canonical_token_count,
                )

    ordered = tuple(
        sorted(outcomes, key=lambda row: (row.document_ref, row.relative_path))
    )
    completed_document_refs = {
        row.document_ref for row in ordered if row.state != "failed"
    }
    if duplicate_occurrences:
        occurrence_store = PostgresCompilerStore.connect(database_url)
        try:
            with occurrence_store.transaction() as cursor:
                for document_ref, relative_path in sorted(duplicate_occurrences):
                    if document_ref not in completed_document_refs:
                        continue
                    occurrence_store.persist_occurrence(
                        cursor,
                        corpus_ref=corpus_ref,
                        relative_path=relative_path,
                        document_ref=document_ref,
                        state="duplicate_content_occurrence",
                    )
        finally:
            occurrence_store.close()
    document_refs = tuple(
        sorted(row.document_ref for row in ordered if row.state != "failed")
    )
    demand_refs = tuple(sorted({ref for row in ordered for ref in row.demand_refs}))
    failure_refs = tuple(
        sorted(row.failure_ref for row in ordered if row.failure_ref is not None)
    )
    return (
        PersistedCompilation(
            corpus_ref=corpus_ref,
            document_refs=document_refs,
            demand_refs=demand_refs,
            failure_refs=failure_refs,
        ),
        ordered,
    )


__all__ = [
    "PARALLEL_COMPILATION_SCHEMA_VERSION",
    "DocumentCompilationOutcome",
    "compile_directory_postgres_parallel",
]
