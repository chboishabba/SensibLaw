"""Process orchestration for streamed typed spaCy parser execution."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from pathlib import Path
from threading import Event, Thread
import time
from time import monotonic_ns
from typing import Any, Callable, Mapping

from src.runtime.durable_work_items import linux_parent_death_initializer
from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    PostgresSentenceCarrier,
    STREAMING_SPACY_CONTRACT,
    build_structural_partitions,
    connect,
    read_partition_text,
    typed_ref,
    write_source,
)
from src.storage.postgres.spacy_parser_store import (
    commit_doc,
    execution_state,
    execution_summary,
    fail_partition,
    lease_partitions,
    recover_expired,
    register_execution,
)


def _renew_batch(
    database_url: str,
    partitions: tuple[Any, ...],
    lease_seconds: int,
    stop: Event,
) -> None:
    interval = max(1.0, lease_seconds / 3)
    while not stop.wait(interval):
        connection = connect(database_url)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    for partition in partitions:
                        cursor.execute(
                            """
                            UPDATE execution.semantic_parser_partition
                            SET lease_expires_at = CURRENT_TIMESTAMP
                                    + (%s * INTERVAL '1 second'),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE partition_ref = %s AND state = 'leased'
                              AND lease_token = %s AND lease_epoch = %s
                            """,
                            (
                                lease_seconds,
                                partition.partition_ref,
                                partition.lease_token,
                                partition.lease_epoch,
                            ),
                        )
        finally:
            connection.close()


def _worker_drain(
    database_url: str,
    run_ref: str,
    worker_ref: str,
    policy: ParserStreamingPolicy,
    artifact_root: str,
) -> int:
    """Load spaCy once and drain leased partitions through one ``Language.pipe``."""

    from src.nlp.spacy_adapter import get_streaming_nlp

    pipeline = get_streaming_nlp()
    completed = 0
    while True:
        partitions = lease_partitions(
            database_url,
            run_ref=run_ref,
            worker_ref=worker_ref,
            batch_size=policy.batch_size,
            lease_seconds=policy.lease_seconds,
        )
        if not partitions:
            return completed
        stop = Event()
        heartbeat = Thread(
            target=_renew_batch,
            args=(database_url, partitions, policy.lease_seconds, stop),
            name=f"spacy-lease-heartbeat-{worker_ref}",
            daemon=True,
        )
        heartbeat.start()
        started: dict[str, int] = {}

        def inputs() -> Any:
            for partition in partitions:
                started[partition.partition_ref] = monotonic_ns()
                yield read_partition_text(partition), partition

        try:
            for doc, partition in pipeline.pipe(
                inputs(),
                as_tuples=True,
                batch_size=policy.batch_size,
                n_process=1,
            ):
                try:
                    commit_doc(
                        database_url,
                        partition=partition,
                        doc=doc,
                        policy=policy,
                        artifact_root=Path(artifact_root),
                        pipeline=pipeline,
                        elapsed_ns=max(
                            0,
                            monotonic_ns()
                            - started.get(partition.partition_ref, monotonic_ns()),
                        ),
                    )
                    completed += 1
                except BaseException as error:
                    fail_partition(
                        database_url,
                        partition=partition,
                        error=error,
                    )
                    raise
        finally:
            stop.set()
            heartbeat.join(timeout=max(2.0, policy.lease_seconds / 2))


def _emit_progress(
    observer: Callable[[Mapping[str, Any]], None] | None,
    *,
    round_ordinal: int,
    state: str,
    ready: int,
    leased: int,
    failed: int,
) -> None:
    if observer is not None:
        observer(
            {
                "current_kernel": "postgresql_streaming_spacy",
                "parser_round_ordinal": round_ordinal,
                "parser_coverage_state": state,
                "parser_partitions_ready": ready,
                "parser_partitions_leased": leased,
                "parser_partitions_failed": failed,
            }
        )


def run_streaming_spacy_execution(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text: str,
    parser_contract_ref: str,
    artifact_root: str | Path,
    worker_count: int = 2,
    policy: ParserStreamingPolicy | None = None,
    progress_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> PostgresSentenceCarrier:
    """Parse one document without constructing a document-sized parser result."""

    if not 1 <= worker_count <= 32:
        raise ValueError("parser worker_count must be between 1 and 32")
    policy = policy or ParserStreamingPolicy()
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    _content_ref, source_path, source_digest, source_bytes = write_source(
        canonical_text,
        root,
    )
    source_ref = typed_ref(
        "parser-source:",
        run_ref,
        document_ref,
        source_digest,
    )
    partitions = build_structural_partitions(
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref=parser_contract_ref,
        canonical_text=canonical_text,
        policy=policy,
    )
    register_execution(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_path=source_path,
        source_digest=source_digest,
        source_bytes=source_bytes,
        source_chars=len(canonical_text),
        parser_contract_ref=parser_contract_ref,
        partitions=partitions,
    )
    state, ready, leased, failed = execution_state(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    _emit_progress(
        progress_observer,
        round_ordinal=-1,
        state=state,
        ready=ready,
        leased=leased,
        failed=failed,
    )
    if failed:
        raise RuntimeError("typed parser partition failed")
    if state != "complete":
        context = mp.get_context("spawn")
        for round_ordinal in range(128):
            with ProcessPoolExecutor(
                max_workers=worker_count,
                mp_context=context,
                initializer=linux_parent_death_initializer,
            ) as pool:
                futures = [
                    pool.submit(
                        _worker_drain,
                        database_url,
                        run_ref,
                        f"parser-worker:{run_ref}:{round_ordinal}:{index}",
                        policy,
                        str(root),
                    )
                    for index in range(worker_count)
                ]
                for future in futures:
                    future.result()
            recover_expired(database_url, run_ref=run_ref)
            state, ready, leased, failed = execution_state(
                database_url,
                run_ref=run_ref,
                document_ref=document_ref,
            )
            _emit_progress(
                progress_observer,
                round_ordinal=round_ordinal,
                state=state,
                ready=ready,
                leased=leased,
                failed=failed,
            )
            if failed:
                raise RuntimeError("typed parser partition failed")
            if state == "complete":
                break
            if ready:
                continue
            if leased:
                time.sleep(min(1.0, policy.lease_seconds / 4))
                continue
            raise RuntimeError("parser coverage remained open without runnable work")
        else:
            raise RuntimeError("parser execution exceeded bounded scheduling rounds")
    summary = execution_summary(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        parser_contract_ref=parser_contract_ref,
    )
    if summary.coverage_state != "complete":
        raise RuntimeError("parser document coverage did not close")
    parser_receipt = {
        "backend_ref": "parser:spacy:typed-postgresql",
        "parser_contract_ref": parser_contract_ref,
        "execution_contract_ref": STREAMING_SPACY_CONTRACT,
        "source_ref": source_ref,
        "sentence_count": summary.sentence_count,
        "token_count": summary.token_count,
        "partition_count": summary.partition_count,
        "entity_count": summary.entity_count,
        "boundary_obligation_count": summary.boundary_obligation_count,
        "coverage_state": summary.coverage_state,
        "authority": "postgresql_typed_parser_observations",
    }
    return PostgresSentenceCarrier(
        database_url=database_url,
        canonical_text=canonical_text,
        summary=summary,
        parser_receipt=parser_receipt,
    )


__all__ = [
    "ParserStreamingPolicy",
    "PostgresSentenceCarrier",
    "STREAMING_SPACY_CONTRACT",
    "run_streaming_spacy_execution",
]
