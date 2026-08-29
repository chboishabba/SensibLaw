"""Gate-A benchmark for the canonical packed-fibre direct architecture.

This is deliberately benchmark-only: it does not change the public execution default.
It uses the real parser partition scheduler and the real hierarchy/reconciliation tail,
but each completed spaCy partition is consumed immediately into packed sentence fibres
and stable-evidence PNF admission while spaCy is allowed to parse the next partition.
A result is returned only after the database proves that no parser sentence/token/entity
observation rows were materialised.

The overlap is the first physical instantiation of the streaming semantic Pac-Man
constitution.  It does not introduce a second compiler: `commit_direct_partition`
remains the semantic/publication owner.  The parser producer is bounded so completed
parser history cannot accumulate unboundedly waiting for a later full compile.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from src.nlp.spacy_adapter import get_streaming_nlp
from src.runtime.overlapped_parser_semantic_stream import (
    Interval,
    ParserStreamActivity,
    stream_parsed_items,
)
from src.storage.postgres.direct_partition_projection import commit_direct_partition
from src.storage.postgres.numeric_adjacent_reconciliation import drain_adjacent_reconciliation
from src.storage.postgres.numeric_hierarchy_planner import materialize_numeric_document_hierarchy
from src.storage.postgres.numeric_hyperfabric_store import (
    hyperfabric_counts,
    register_authored_hierarchy,
)
from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    build_structural_partitions,
    connect,
    read_partition_text,
    typed_ref,
    write_source,
)
from src.storage.postgres.spacy_parser_registration import register_or_reuse_execution
from src.storage.postgres.spacy_parser_store import (
    execution_state,
    fail_partition,
    lease_partitions,
)


@dataclass(frozen=True, slots=True)
class DirectGateABenchmarkReceipt:
    run_ref: str
    document_ref: str
    sentence_count: int
    token_count: int
    partition_count: int
    stable_evidence_rows: int
    parser_sentence_rows: int
    parser_token_rows: int
    parser_entity_rows: int
    local_database_crossings: int
    spacy_ns: int
    direct_total_ns: int
    local_publish_ns: int
    hierarchy_reconcile_ns: int
    r_direct: float
    first_stage_target_met: bool
    coverage_state: str
    pnf_region_count: int
    pnf_object_count: int
    pnf_factor_count: int
    pnf_demand_count: int
    parser_semantic_overlap_ns: int
    semantic_sentences_at_parser_eof: int
    stream_completion_fraction: float
    post_parser_tail_ns: int
    phase_accounting: str = "overlapped_active_time"


def _preflight_direct_schema(database_url: str) -> None:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT to_regclass('execution.semantic_source_token_evidence'),
                       to_regclass('execution.semantic_pnf_object_evidence_support'),
                       to_regclass('execution.semantic_pnf_factor_evidence_support')
                """
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None or any(value is None for value in row):
        raise RuntimeError(
            "canonical Gate-A schema is missing; apply migration 212 before benchmarking"
        )


def _drain_adjacent(database_url: str, *, run_ref: str, stage: str) -> int:
    total = 0
    while True:
        summary = drain_adjacent_reconciliation(
            database_url,
            run_ref=run_ref,
            worker_ref=f"gate-a:{run_ref}:adjacent:{stage}",
            limit=256,
        )
        total += summary.completed_pairs
        if summary.completed_pairs == 0:
            return total


def _refresh_lookup(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> int:
    connection = connect(database_url)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT execution.refresh_pnf_global_lookup(%s, %s)",
                    (run_ref, document_ref),
                )
                row = cursor.fetchone()
                return int(row[0]) if row is not None else 0
    finally:
        connection.close()


def _gate_counts(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[int, int, int, int, int, int, int]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM execution.semantic_parser_sentence
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_parser_token
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_parser_entity_span
                      WHERE run_ref = %s AND document_ref = %s),
                    (SELECT count(*) FROM execution.semantic_source_token_evidence
                      WHERE run_ref = %s AND document_ref = %s),
                    COALESCE((SELECT sum(sentence_count)
                      FROM execution.semantic_parser_partition_receipt
                      WHERE run_ref = %s AND document_ref = %s), 0),
                    COALESCE((SELECT sum(token_count)
                      FROM execution.semantic_parser_partition_receipt
                      WHERE run_ref = %s AND document_ref = %s), 0),
                    (SELECT count(*) FROM execution.semantic_parser_partition
                      WHERE run_ref = %s AND document_ref = %s)
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
                    run_ref,
                    document_ref,
                    run_ref,
                    document_ref,
                ),
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("Gate-A database receipt is missing")
    return tuple(int(value) for value in row)  # type: ignore[return-value]


def _overlap_duration(left: tuple[Interval, ...], right: tuple[Interval, ...]) -> int:
    total = 0
    for left_start, left_end in left:
        for right_start, right_end in right:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if end > start:
                total += end - start
    return total


def run_direct_gate_a_benchmark(
    *,
    database_url: str,
    run_ref: str,
    document_ref: str,
    canonical_text: str,
    parser_contract_ref: str,
    artifact_root: str | Path,
    policy: ParserStreamingPolicy | None = None,
) -> DirectGateABenchmarkReceipt:
    """Run one fresh canonical direct benchmark and return its proof-bearing receipt.

    Parser and direct partition publication overlap through a bounded one-item
    queue.  `spacy_ns` and `local_publish_ns` are therefore active-time phase
    measurements and may overlap; they are not expected to sum to wall time.
    `direct_total_ns` remains end-to-end wall time.
    """

    if not canonical_text:
        raise ValueError("Gate-A benchmark requires non-empty canonical text")
    _preflight_direct_schema(database_url)
    policy = policy or ParserStreamingPolicy()
    root = Path(artifact_root)
    root.mkdir(parents=True, exist_ok=True)

    pipeline = get_streaming_nlp()
    _content_ref, source_path, source_digest, source_bytes = write_source(
        canonical_text, root
    )
    source_ref = typed_ref("parser-source:", run_ref, document_ref, source_digest)
    proposed = build_structural_partitions(
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_locator=str(source_path),
        parser_contract_ref=parser_contract_ref,
        canonical_text=canonical_text,
        policy=policy,
    )
    register_or_reuse_execution(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        source_path=source_path,
        source_digest=source_digest,
        source_bytes=source_bytes,
        source_chars=len(canonical_text),
        parser_contract_ref=parser_contract_ref,
        proposed_partitions=proposed,
    )
    register_authored_hierarchy(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
        canonical_text=canonical_text,
        execution_window_chars=max(65_536, policy.target_chars * 2),
    )

    total_started = monotonic_ns()
    parser_intervals: list[Interval] = []
    publish_intervals: list[Interval] = []
    published_sentence_intervals: list[tuple[int, int, int]] = []
    parser_finished_ns: int | None = None
    published_sentences = 0
    local_publish_ns = 0

    for round_ordinal in range(128):
        partitions = lease_partitions(
            database_url,
            run_ref=run_ref,
            worker_ref=f"gate-a:{run_ref}:{round_ordinal}",
            batch_size=policy.batch_size,
            lease_seconds=policy.lease_seconds,
        )
        if not partitions:
            state, ready, leased, failed = execution_state(
                database_url,
                run_ref=run_ref,
                document_ref=document_ref,
            )
            if failed:
                raise RuntimeError("Gate-A direct partition failed")
            if state == "complete":
                break
            if ready or leased:
                continue
            raise RuntimeError("Gate-A coverage remained open without runnable work")

        inputs = tuple(
            (read_partition_text(partition), partition) for partition in partitions
        )
        activity = ParserStreamActivity()
        for item in stream_parsed_items(
            pipeline,
            inputs,
            batch_size=policy.batch_size,
            queue_size=1,
            activity=activity,
        ):
            doc = item.doc
            partition = item.context
            try:
                publish_started = monotonic_ns()
                sentence_count_for_partition = commit_direct_partition(
                    database_url,
                    partition=partition,
                    doc=doc,
                    policy=policy,
                    artifact_root=root,
                    pipeline=pipeline,
                    elapsed_ns=max(0, item.parser_interval[1] - item.parser_interval[0]),
                )
                publish_finished = monotonic_ns()
                local_publish_ns += publish_finished - publish_started
                publish_intervals.append((publish_started, publish_finished))
                published_sentence_intervals.append(
                    (publish_started, publish_finished, sentence_count_for_partition)
                )
                published_sentences += sentence_count_for_partition
            except BaseException as error:
                fail_partition(database_url, partition=partition, error=error)
                raise
        parser_intervals.extend(activity.intervals)
        if activity.finished_ns is not None:
            parser_finished_ns = activity.finished_ns
    else:
        raise RuntimeError("Gate-A direct execution exceeded bounded scheduling rounds")

    local_publish_finished = monotonic_ns()
    _drain_adjacent(database_url, run_ref=run_ref, stage="sentence")
    materialize_numeric_document_hierarchy(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    _drain_adjacent(database_url, run_ref=run_ref, stage="paragraph")
    _refresh_lookup(database_url, run_ref=run_ref, document_ref=document_ref)
    direct_finished = monotonic_ns()
    direct_total_ns = max(0, direct_finished - total_started)
    hierarchy_reconcile_ns = max(0, direct_finished - local_publish_finished)
    spacy_ns = sum(max(0, end - start) for start, end in parser_intervals)
    parser_semantic_overlap_ns = _overlap_duration(
        tuple(parser_intervals), tuple(publish_intervals)
    )

    state, _ready, _leased, failed = execution_state(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    if state != "complete" or failed:
        raise RuntimeError(
            f"Gate-A coverage did not close: state={state!r} failed={failed}"
        )

    (
        parser_sentence_rows,
        parser_token_rows,
        parser_entity_rows,
        stable_evidence_rows,
        sentence_count,
        token_count,
        partition_count,
    ) = _gate_counts(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    if parser_sentence_rows or parser_token_rows or parser_entity_rows:
        raise RuntimeError(
            "Gate-A violated zero parser observation projection: "
            f"sentences={parser_sentence_rows} tokens={parser_token_rows} "
            f"entities={parser_entity_rows}"
        )
    if stable_evidence_rows == 0 or published_sentences == 0:
        raise RuntimeError(
            "Gate-A direct execution produced no stable semantic evidence"
        )
    if spacy_ns <= 0:
        raise RuntimeError("Gate-A spaCy timing receipt is empty")

    parser_eof = parser_finished_ns or total_started
    semantic_sentences_at_parser_eof = sum(
        count
        for _started, finished, count in published_sentence_intervals
        if finished <= parser_eof
    )
    stream_completion_fraction = semantic_sentences_at_parser_eof / max(
        1, published_sentences
    )
    post_parser_tail_ns = max(0, direct_finished - parser_eof)

    counts = hyperfabric_counts(
        database_url,
        run_ref=run_ref,
        document_ref=document_ref,
    )
    ratio = direct_total_ns / spacy_ns
    return DirectGateABenchmarkReceipt(
        run_ref=run_ref,
        document_ref=document_ref,
        sentence_count=sentence_count,
        token_count=token_count,
        partition_count=partition_count,
        stable_evidence_rows=stable_evidence_rows,
        parser_sentence_rows=parser_sentence_rows,
        parser_token_rows=parser_token_rows,
        parser_entity_rows=parser_entity_rows,
        local_database_crossings=0,
        spacy_ns=spacy_ns,
        direct_total_ns=direct_total_ns,
        local_publish_ns=local_publish_ns,
        hierarchy_reconcile_ns=hierarchy_reconcile_ns,
        r_direct=ratio,
        first_stage_target_met=ratio <= 2.0,
        coverage_state=state,
        pnf_region_count=counts["regions"],
        pnf_object_count=counts["objects"],
        pnf_factor_count=counts["factors"],
        pnf_demand_count=counts["demands"],
        parser_semantic_overlap_ns=parser_semantic_overlap_ns,
        semantic_sentences_at_parser_eof=semantic_sentences_at_parser_eof,
        stream_completion_fraction=stream_completion_fraction,
        post_parser_tail_ns=post_parser_tail_ns,
    )


__all__ = ["DirectGateABenchmarkReceipt", "run_direct_gate_a_benchmark"]
