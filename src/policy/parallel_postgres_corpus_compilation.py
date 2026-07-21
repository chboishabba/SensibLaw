"""Bounded document-level PostgreSQL compilation with deterministic reduction.

Corpus admission and the final result ordering remain serialized. Each worker owns a
short-lived PostgreSQL connection and compiles exactly one immutable document build.
No worker mutates a shared graph object or a mutable corpus pointer.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic, monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.operational_corpus_compilation import OPERATIONAL_COMPILER_CONTRACT
from src.policy.postgres_corpus_compilation import (
    _operational_build_key,
    _prepare_operational_manifest,
    persist_document_compilation,
)
from src.runtime.compiler_progress import compiler_progress_callback
from src.runtime.progress import PhaseHandle
from src.storage.postgres import PersistedCompilation, PostgresCompilerStore
from src.storage.postgres.operational_build_store import load_completed_operational_build


PARALLEL_COMPILATION_SCHEMA_VERSION = "sl.parallel_postgres_compilation.v0_2"


@dataclass(frozen=True)
class DocumentCompilationOutcome:
    document_ref: str
    relative_path: str
    state: str
    demand_refs: tuple[str, ...] = ()
    failure_ref: str | None = None
    elapsed_ms: int = 0
    worker: str = ""
    token_count: int = 0
    final_stage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PARALLEL_COMPILATION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "relative_path": self.relative_path,
            "state": self.state,
            "demand_refs": list(self.demand_refs),
            "failure_ref": self.failure_ref,
            "elapsed_ms": self.elapsed_ms,
            "worker": self.worker,
            "token_count": self.token_count,
            "final_stage": self.final_stage,
        }


@dataclass
class CompilationTelemetry:
    total_documents: int
    started_at: float = field(default_factory=monotonic)
    token_count_by_document: dict[str, int] = field(default_factory=dict)
    completed_tokens_by_document: dict[str, int] = field(default_factory=dict)
    stage_by_document: dict[str, str] = field(default_factory=dict)
    completed_documents: int = 0
    failed_documents: int = 0
    lock: Lock = field(default_factory=Lock)

    def observe(self, payload: Mapping[str, Any]) -> None:
        document_ref = str(payload.get("document_ref") or "")
        if not document_ref:
            return
        with self.lock:
            self.stage_by_document[document_ref] = str(payload.get("stage") or "")
            if payload.get("token_count") is not None:
                self.token_count_by_document[document_ref] = max(
                    self.token_count_by_document.get(document_ref, 0),
                    int(payload["token_count"]),
                )
            if payload.get("completed_tokens") is not None:
                self.completed_tokens_by_document[document_ref] = max(
                    self.completed_tokens_by_document.get(document_ref, 0),
                    int(payload["completed_tokens"]),
                )

    def complete(self, outcome: DocumentCompilationOutcome) -> None:
        with self.lock:
            self.completed_documents += 1
            self.failed_documents += int(outcome.state == "failed")
            if outcome.token_count:
                self.token_count_by_document[outcome.document_ref] = outcome.token_count
            self.stage_by_document[outcome.document_ref] = outcome.final_stage or outcome.state

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            elapsed = max(monotonic() - self.started_at, 0.001)
            tokenized_tokens = sum(self.token_count_by_document.values())
            completed_tokens = sum(self.completed_tokens_by_document.values())
            document_rate = self.completed_documents / elapsed
            remaining = max(0, self.total_documents - self.completed_documents)
            eta_seconds = remaining / document_rate if document_rate > 0 else None
            stage_counts: dict[str, int] = {}
            for stage in self.stage_by_document.values():
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
            return {
                "heartbeat": True,
                "completed_documents": self.completed_documents,
                "failed_documents": self.failed_documents,
                "total_documents": self.total_documents,
                "tokenized_tokens": tokenized_tokens,
                "completed_tokens": completed_tokens,
                "tokenization_tps": round(tokenized_tokens / elapsed, 3),
                "semantic_completion_tps": round(completed_tokens / elapsed, 3),
                "documents_per_second": round(document_rate, 6),
                "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
                "active_stage_counts": {key: stage_counts[key] for key in sorted(stage_counts)},
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
    telemetry: CompilationTelemetry,
) -> DocumentCompilationOutcome:
    started = monotonic_ns()
    document_ref = str(entry["document_ref"])
    relative_path = str(entry["relative_path"])
    store = PostgresCompilerStore.connect(database_url)
    final_stage = "admitted"
    token_count = 0

    def observe(payload: Mapping[str, Any]) -> None:
        nonlocal final_stage, token_count
        final_stage = str(payload.get("stage") or final_stage)
        if payload.get("token_count") is not None:
            token_count = max(token_count, int(payload["token_count"]))
        telemetry.observe(payload)

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
        with compiler_progress_callback(observe):
            demand_refs = persist_document_compilation(
                store=store,
                corpus_ref=corpus_ref,
                relative_path=relative_path,
                entry=entry,
                source_bytes=source_bytes,
                source_text=source_text,
                context=context,
            )
        outcome = DocumentCompilationOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="reused" if cached is not None else "compiled",
            demand_refs=tuple(sorted(set(demand_refs))),
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            worker=worker,
            token_count=token_count,
            final_stage=final_stage,
        )
        telemetry.complete(outcome)
        return outcome
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as error:
        with store.transaction() as cursor:
            failure_ref = store.persist_failure(
                cursor,
                target_ref=document_ref,
                phase_ref="local_compile",
                error=error,
            )
        outcome = DocumentCompilationOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="failed",
            failure_ref=failure_ref,
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            worker=worker,
            token_count=token_count,
            final_stage=final_stage,
        )
        telemetry.complete(outcome)
        return outcome
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
    heartbeat_interval_seconds: float = 30.0,
) -> tuple[PersistedCompilation, tuple[DocumentCompilationOutcome, ...]]:
    """Compile distinct canonical documents concurrently and reduce stably.

    Heartbeats distinguish tokenization throughput from semantically completed token
    throughput. A document that has tokenized but remains in parsing or local typing is
    visible without pretending its semantic build has completed.
    """

    phases = {"inventory", "local", "demand_planning", "legal_catalogue_build"}
    if execution_phase not in phases:
        raise ValueError("unsupported corpus compilation phase")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    if heartbeat_interval_seconds <= 0:
        raise ValueError("heartbeat interval must be positive")

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
        seen: set[str] = set()
        for entry in manifest_row["ordered_documents"]:
            if entry["status"] != "inventoried":
                continue
            document_ref = str(entry["document_ref"])
            relative_path = str(entry["relative_path"])
            if document_ref in seen:
                with admission_store.transaction() as cursor:
                    admission_store.persist_occurrence(
                        cursor,
                        corpus_ref=corpus_ref,
                        relative_path=relative_path,
                        document_ref=document_ref,
                        state="duplicate_content_occurrence",
                    )
                continue
            seen.add(document_ref)
            admitted.append(entry)
    finally:
        admission_store.close()

    if progress is not None:
        progress.total = len(admitted)

    telemetry = CompilationTelemetry(total_documents=len(admitted))
    stop_heartbeat = Event()

    def heartbeat() -> None:
        while not stop_heartbeat.wait(heartbeat_interval_seconds):
            if progress is not None:
                progress.advance(
                    amount=0,
                    message="compiler heartbeat",
                    details=telemetry.snapshot(),
                )

    heartbeat_thread = Thread(target=heartbeat, name="pnf-heartbeat", daemon=True)
    heartbeat_thread.start()
    outcomes: list[DocumentCompilationOutcome] = []
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pnf-document") as executor:
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
                    telemetry=telemetry,
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
                            "token_count": outcome.token_count,
                            "final_stage": outcome.final_stage,
                            **telemetry.snapshot(),
                        },
                    )
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=max(1.0, heartbeat_interval_seconds))

    ordered = tuple(sorted(outcomes, key=lambda row: (row.document_ref, row.relative_path)))
    document_refs = tuple(sorted(row.document_ref for row in ordered if row.state != "failed"))
    demand_refs = tuple(sorted({ref for row in ordered for ref in row.demand_refs}))
    failure_refs = tuple(sorted(row.failure_ref for row in ordered if row.failure_ref is not None))
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
    "CompilationTelemetry",
    "DocumentCompilationOutcome",
    "compile_directory_postgres_parallel",
]
