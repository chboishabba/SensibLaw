"""Timeout-safe parser timing diagnostics from durable partition receipts.

The parser receipt elapsed time is measured directly around spaCy iteration and
is therefore useful partial evidence even when the wider numeric pipeline does
not complete. Partition work time is deliberately not promoted to wall
occupancy: concurrent parser fibres can overlap and the durable receipt does not
carry their monotonic start/end coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.storage.postgres.spacy_parser_model import connect


PARTIAL_PARSER_TIMING_SCHEMA = "sensiblaw.partial-parser-timing.v0_1"


@dataclass(frozen=True, slots=True)
class ParserPartitionTiming:
    partition_ref: str
    token_count: int
    sentence_count: int
    elapsed_ns: int
    worker_pid: int
    backend_pid: int | None


def summarize_partition_timings(
    rows: Iterable[ParserPartitionTiming],
) -> dict[str, Any]:
    partitions = tuple(rows)
    parser_work_ns = sum(max(0, item.elapsed_ns) for item in partitions)
    token_count = sum(max(0, item.token_count) for item in partitions)
    sentence_count = sum(max(0, item.sentence_count) for item in partitions)
    worker_pids = sorted({item.worker_pid for item in partitions})
    return {
        "schema_version": PARTIAL_PARSER_TIMING_SCHEMA,
        "state": "partial_diagnostic_only",
        "acceptance_eligible": False,
        "parser_relative_gate_eligible": False,
        "partition_count": len(partitions),
        "token_count": token_count,
        "sentence_count": sentence_count,
        "spacy_parser_work_ns": parser_work_ns,
        "max_partition_spacy_ns": max(
            (item.elapsed_ns for item in partitions), default=0
        ),
        "worker_pids": worker_pids,
        "tokens_per_parser_work_second": (
            token_count / (parser_work_ns / 1_000_000_000)
            if parser_work_ns > 0
            else None
        ),
        "spacy_parser_wall_occupancy_ns": None,
        "wall_occupancy_state": "unknown_without_monotonic_partition_intervals",
        "concurrent_partition_work_ns_must_not_be_treated_as_wall": True,
        "semantic_authority_effect": "none",
        "semantic_identity_effect": "none",
    }


def load_partial_parser_timing(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> Mapping[str, Any]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT receipt.partition_ref,
                       receipt.token_count,
                       receipt.sentence_count,
                       receipt.elapsed_ns,
                       receipt.worker_pid,
                       receipt.backend_pid
                  FROM execution.semantic_parser_partition_receipt AS receipt
                 WHERE receipt.run_ref = %s
                   AND receipt.document_ref = %s
                 ORDER BY receipt.completed_at, receipt.partition_ref
                """,
                (run_ref, document_ref),
            )
            rows = tuple(
                ParserPartitionTiming(
                    partition_ref=str(partition_ref),
                    token_count=int(token_count),
                    sentence_count=int(sentence_count),
                    elapsed_ns=int(elapsed_ns),
                    worker_pid=int(worker_pid),
                    backend_pid=(None if backend_pid is None else int(backend_pid)),
                )
                for (
                    partition_ref,
                    token_count,
                    sentence_count,
                    elapsed_ns,
                    worker_pid,
                    backend_pid,
                ) in cursor.fetchall()
            )
    finally:
        connection.close()
    result = dict(summarize_partition_timings(rows))
    result.update({"run_ref": run_ref, "document_ref": document_ref})
    return result


__all__ = [
    "PARTIAL_PARSER_TIMING_SCHEMA",
    "ParserPartitionTiming",
    "load_partial_parser_timing",
    "summarize_partition_timings",
]
