"""Curated offline corpus compilation with admission and bounded retry.

The parser pool sees only revisions carrying an immutable ``compile`` admission
receipt. Evidence-only and excluded artefacts remain in the admission manifest
and never enter canonical parsing or PNF construction.
"""

from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic_ns, sleep
from typing import Any, Callable, Mapping, Sequence

from psycopg import Error as PostgresError

from src.policy.corpus_compilation import CompilerContext, build_corpus_manifest
from src.policy.fibred_operational_corpus_compilation import (
    FIBRED_OPERATIONAL_COMPILER_CONTRACT,
)
from src.policy.optimized_streaming_postgres_corpus_compilation import (
    persist_optimized_streaming_document_compilation,
)
from src.policy.postgres_corpus_compilation import (
    _operational_build_key,
    _prepare_operational_manifest,
)
from src.runtime.progress import PhaseHandle
from src.sensiblaw.interfaces import tokenize_canonical_with_spans
from src.sources.admission import (
    SourceAdmissionProfile,
    SourceAdmissionReceipt,
    admission_manifest,
    admit_source,
)
from src.storage.postgres import PersistedCompilation
from src.storage.postgres.batched_compiler_store import BatchedPostgresCompilerStore
from src.storage.postgres.legal_source_store import (
    persist_source_admission_receipts,
    persist_transaction_attempt,
)
from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
)
from src.storage.postgres.streaming_semantic_store import load_stage_timings

_RETRYABLE_SQLSTATES = {"40001", "40P01"}
CURATED_COMPILATION_SCHEMA_VERSION = "sl.curated_postgres_compilation.v0_1"


@dataclass(frozen=True)
class CuratedDocumentOutcome:
    document_ref: str
    relative_path: str
    state: str
    admission_receipt_ref: str
    demand_refs: tuple[str, ...] = ()
    failure_ref: str | None = None
    elapsed_ms: int = 0
    canonical_token_count: int = 0
    worker: str = ""
    stage_timings: tuple[Mapping[str, Any], ...] = ()
    retry_count: int = 0
    transaction_attempt_refs: tuple[str, ...] = ()
    closure_workers: int = 1
    owner_partitions: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CURATED_COMPILATION_SCHEMA_VERSION,
            **asdict(self),
            "demand_refs": list(self.demand_refs),
            "stage_timings": [dict(row) for row in self.stage_timings],
            "transaction_attempt_refs": list(self.transaction_attempt_refs),
        }


@dataclass(frozen=True)
class CuratedCompilationResult:
    persisted: PersistedCompilation
    outcomes: tuple[CuratedDocumentOutcome, ...]
    admission: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CURATED_COMPILATION_SCHEMA_VERSION,
            "persisted": asdict(self.persisted),
            "outcomes": [row.to_dict() for row in self.outcomes],
            "admission": dict(self.admission),
        }


def _build_key(entry: Mapping[str, Any], context: CompilerContext) -> str:
    return _operational_build_key(
        document_ref=str(entry["document_ref"]),
        content_sha256=str(entry["content_sha256"]),
        canonical_text_sha256=str(entry["canonical_text_sha256"]),
        media_adapter_ref=str(entry["media_adapter_ref"]),
        context=context,
    )


def _retry_delay_ms(document_ref: str, attempt_no: int) -> int:
    from src.policy.carriers.canonical import canonical_sha256

    jitter = int(canonical_sha256({"document_ref": document_ref, "attempt": attempt_no})[:4], 16) % 37
    return min(1000, 50 * attempt_no + jitter)


def _persist_attempt(
    store: BatchedPostgresCompilerStore,
    *,
    document_ref: str,
    build_key_sha256: str,
    attempt_no: int,
    state: str,
    sqlstate: str | None,
    retry_delay_ms: int,
    worker_ref: str,
) -> str:
    with store.transaction() as cursor:
        return persist_transaction_attempt(
            cursor,
            document_ref=document_ref,
            build_key_sha256=build_key_sha256,
            attempt_no=attempt_no,
            state=state,
            sqlstate=sqlstate,
            retry_delay_ms=retry_delay_ms,
            worker_ref=worker_ref,
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
    admission_receipt_ref: str,
    closure_workers: int,
    owner_partitions: int,
    maximum_transaction_attempts: int,
) -> CuratedDocumentOutcome:
    started = monotonic_ns()
    document_ref = str(entry["document_ref"])
    relative_path = str(entry["relative_path"])
    build_key = _build_key(entry, context)
    store = BatchedPostgresCompilerStore.connect(database_url)
    attempt_refs: list[str] = []
    try:
        with store.transaction() as cursor:
            cached = load_completed_operational_build(
                cursor,
                document_ref=document_ref,
                compiler_contract_ref=FIBRED_OPERATIONAL_COMPILER_CONTRACT,
                build_key_sha256=build_key,
            )
        if prepared_source is None:
            source_bytes = (root / relative_path).read_bytes()
            source_text = source_bytes.decode("utf-8")
        else:
            source_bytes, source_text = prepared_source

        demand_refs: tuple[str, ...] = ()
        for attempt_no in range(1, maximum_transaction_attempts + 1):
            try:
                demand_refs = persist_optimized_streaming_document_compilation(
                    store=store,
                    corpus_ref=corpus_ref,
                    relative_path=relative_path,
                    entry=entry,
                    source_bytes=source_bytes,
                    source_text=source_text,
                    context=context,
                    closure_workers=closure_workers,
                    owner_partitions=owner_partitions,
                )
                attempt_refs.append(
                    _persist_attempt(
                        store,
                        document_ref=document_ref,
                        build_key_sha256=build_key,
                        attempt_no=attempt_no,
                        state="succeeded",
                        sqlstate=None,
                        retry_delay_ms=0,
                        worker_ref=worker,
                    )
                )
                break
            except PostgresError as error:
                sqlstate = getattr(error, "sqlstate", None)
                retryable = sqlstate in _RETRYABLE_SQLSTATES
                final_attempt = attempt_no >= maximum_transaction_attempts
                delay_ms = 0 if final_attempt or not retryable else _retry_delay_ms(document_ref, attempt_no)
                attempt_refs.append(
                    _persist_attempt(
                        store,
                        document_ref=document_ref,
                        build_key_sha256=build_key,
                        attempt_no=attempt_no,
                        state=(
                            "retryable_failure"
                            if retryable and not final_attempt
                            else "failed"
                        ),
                        sqlstate=sqlstate,
                        retry_delay_ms=delay_ms,
                        worker_ref=worker,
                    )
                )
                if not retryable or final_attempt:
                    raise
                sleep(delay_ms / 1000.0)
        with store.transaction() as cursor:
            canonical_token_count = store.count_persisted_tokens(
                cursor,
                document_ref=document_ref,
            )
            stage_timings = load_stage_timings(cursor, document_ref=document_ref)
        return CuratedDocumentOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="reused" if cached is not None else "compiled",
            admission_receipt_ref=admission_receipt_ref,
            demand_refs=tuple(sorted(set(demand_refs))),
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            canonical_token_count=canonical_token_count,
            worker=worker,
            stage_timings=stage_timings,
            retry_count=max(0, len(attempt_refs) - 1),
            transaction_attempt_refs=tuple(attempt_refs),
            closure_workers=closure_workers,
            owner_partitions=owner_partitions,
        )
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError, PostgresError) as error:
        with store.transaction() as cursor:
            failure_ref = store.persist_failure(
                cursor,
                target_ref=document_ref,
                phase_ref="curated_local_compile",
                error=error,
            )
        return CuratedDocumentOutcome(
            document_ref=document_ref,
            relative_path=relative_path,
            state="failed",
            admission_receipt_ref=admission_receipt_ref,
            failure_ref=failure_ref,
            elapsed_ms=max(0, (monotonic_ns() - started) // 1_000_000),
            worker=worker,
            retry_count=max(0, len(attempt_refs) - 1),
            transaction_attempt_refs=tuple(attempt_refs),
            closure_workers=closure_workers,
            owner_partitions=owner_partitions,
        )
    finally:
        store.close()


def compile_curated_directory_postgres(
    input_dir: str | Path,
    *,
    context: CompilerContext,
    database_url: str,
    admission_profile: SourceAdmissionProfile,
    source_metadata: Mapping[str, Mapping[str, Any]],
    workers: int = 4,
    closure_workers_per_document: int = 4,
    owner_partitions_per_document: int = 8,
    maximum_transaction_attempts: int = 3,
    recursive: bool = True,
    include_globs: Sequence[str] = (),
    exclude_globs: Sequence[str] = (),
    max_files: int | None = None,
    max_file_bytes: int | None = None,
    max_total_bytes: int | None = None,
    progress: PhaseHandle | None = None,
    outcome_sink: Callable[[CuratedDocumentOutcome], None] | None = None,
) -> CuratedCompilationResult:
    """Compile only source revisions admitted by the supplied profile."""

    if not 1 <= workers <= 32:
        raise ValueError("workers must be between 1 and 32")
    if not 1 <= closure_workers_per_document <= 32:
        raise ValueError("closure workers must be between 1 and 32")
    if not 1 <= owner_partitions_per_document <= 128:
        raise ValueError("owner partitions must be between 1 and 128")
    if not 1 <= maximum_transaction_attempts <= 8:
        raise ValueError("transaction attempts must be between 1 and 8")

    root = Path(input_dir).resolve()
    manifest = build_corpus_manifest(
        root,
        context=context,
        recursive=recursive,
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
    receipts: list[SourceAdmissionReceipt] = []
    admitted: list[tuple[Mapping[str, Any], SourceAdmissionReceipt]] = []
    seen_documents: set[str] = set()
    for entry in manifest_row["ordered_documents"]:
        if entry["status"] != "inventoried":
            continue
        relative_path = str(entry["relative_path"])
        metadata = dict(source_metadata.get(relative_path) or {})
        metadata.update(
            {
                "document_ref": entry["document_ref"],
                "source_revision_ref": (
                    metadata.get("source_revision_ref")
                    or f"source-revision:{entry['content_sha256']}"
                ),
            }
        )
        receipt = admit_source(metadata, profile=admission_profile)
        receipts.append(receipt)
        if not receipt.compile_eligible:
            continue
        document_ref = str(entry["document_ref"])
        if document_ref in seen_documents:
            continue
        seen_documents.add(document_ref)
        admitted.append((entry, receipt))

    admission_store = BatchedPostgresCompilerStore.connect(database_url)
    try:
        with admission_store.transaction() as cursor:
            admission_store.persist_context(cursor, context.to_dict())
            admission_store.persist_manifest(cursor, manifest_row)
            persist_source_admission_receipts(
                cursor,
                corpus_ref=corpus_ref,
                receipts=receipts,
            )
    finally:
        admission_store.close()

    if progress is not None:
        progress.total = len(admitted)
        progress.total_tokens = sum(
            len(tokenize_canonical_with_spans(prepared_sources[str(entry["relative_path"])][1]))
            for entry, _ in admitted
        )

    outcomes: list[CuratedDocumentOutcome] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures: dict[Future[CuratedDocumentOutcome], str] = {}
        for index, (entry, receipt) in enumerate(admitted):
            relative_path = str(entry["relative_path"])
            future = executor.submit(
                _compile_one,
                database_url=database_url,
                corpus_ref=corpus_ref,
                root=root,
                entry=entry,
                prepared_source=prepared_sources.get(relative_path),
                context=context,
                worker=f"document-{(index % workers) + 1}",
                admission_receipt_ref=receipt.receipt_ref,
                closure_workers=closure_workers_per_document,
                owner_partitions=owner_partitions_per_document,
                maximum_transaction_attempts=maximum_transaction_attempts,
            )
            futures[future] = str(entry["document_ref"])
        for future in as_completed(futures):
            outcome = future.result()
            outcomes.append(outcome)
            if outcome_sink is not None:
                outcome_sink(outcome)
            if progress is not None:
                progress.advance(
                    subject_ref=outcome.document_ref,
                    message=outcome.state,
                    reused=outcome.state == "reused",
                    processed_tokens=outcome.canonical_token_count,
                    details={
                        "relative_path": outcome.relative_path,
                        "worker": outcome.worker,
                        "retry_count": outcome.retry_count,
                        "failure_ref": outcome.failure_ref,
                    },
                )

    ordered = tuple(sorted(outcomes, key=lambda row: (row.document_ref, row.relative_path)))
    persisted = PersistedCompilation(
        corpus_ref=corpus_ref,
        document_refs=tuple(sorted(row.document_ref for row in ordered if row.state != "failed")),
        demand_refs=tuple(sorted({ref for row in ordered for ref in row.demand_refs})),
        failure_refs=tuple(
            sorted(row.failure_ref for row in ordered if row.failure_ref is not None)
        ),
    )
    return CuratedCompilationResult(
        persisted=persisted,
        outcomes=ordered,
        admission=admission_manifest(receipts),
    )


__all__ = [
    "CURATED_COMPILATION_SCHEMA_VERSION",
    "CuratedCompilationResult",
    "CuratedDocumentOutcome",
    "compile_curated_directory_postgres",
]
