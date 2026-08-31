#!/usr/bin/env python3
"""Run the canonical packed-fibre Gate-A benchmark against a migrated database."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import traceback
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.runtime.diagnostic_bundle import (
    bundle_artifact_directory,
    write_json_receipt,
)
from src.runtime.parser_schedule_parity_preflight import run_schedule_parity_preflight
from src.runtime.streaming_overlap_evidence import partition_aware_eof_overlap
from src.runtime.streaming_partition_refinement import (
    partition_geometry,
    target_chars_for_partition_count,
)
from src.storage.postgres.direct_gate_a_benchmark import run_direct_gate_a_benchmark
from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy, connect


_COARSE_TARGET_CHARS = 32_768


def _partition_sentence_counts(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[int, ...]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(r.sentence_count, 0)
                  FROM execution.semantic_parser_partition AS p
                  LEFT JOIN execution.semantic_parser_partition_receipt AS r
                    ON r.partition_ref = p.partition_ref
                 WHERE p.run_ref = %s
                   AND p.document_ref = %s
                 ORDER BY p.sequence_no, p.partition_ref
                """,
                (run_ref, document_ref),
            )
            return tuple(int(row[0]) for row in cursor.fetchall())
    finally:
        connection.close()


def _structural_partition_intervals(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[tuple[int, int, int, int], ...]:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT owner_start_char, owner_end_char,
                       context_start_char, context_end_char
                  FROM execution.semantic_parser_partition
                 WHERE run_ref = %s
                   AND document_ref = %s
                   AND partition_kind = 'structural'
                 ORDER BY owner_start_char, owner_end_char, partition_ref
                """,
                (run_ref, document_ref),
            )
            return tuple(tuple(int(value) for value in row) for row in cursor.fetchall())
    finally:
        connection.close()


def _physical_parser_context_chars(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> int:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(sum(context_end_char - context_start_char), 0)
                  FROM execution.semantic_parser_partition
                 WHERE run_ref = %s
                   AND document_ref = %s
                   AND state = 'completed'
                """,
                (run_ref, document_ref),
            )
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0
    finally:
        connection.close()


def _run(args: argparse.Namespace) -> dict[str, object]:
    text = args.text_file.read_text(encoding="utf-8")
    target_chars = args.target_chars
    if args.target_partitions is not None:
        target_chars = target_chars_for_partition_count(
            source_chars=len(text),
            target_partitions=args.target_partitions,
        )

    schedule_parity = None
    if target_chars != _COARSE_TARGET_CHARS:
        schedule_parity = run_schedule_parity_preflight(
            text,
            coarse_target_chars=_COARSE_TARGET_CHARS,
            candidate_target_chars=target_chars,
            context_chars=args.context_chars,
        )

    policy = ParserStreamingPolicy(
        target_chars=target_chars,
        context_chars=args.context_chars,
        batch_size=args.batch_size,
        lease_seconds=args.lease_seconds,
    )
    run_ref = args.run_ref or f"gate-a-direct:{uuid4().hex}"

    prior_pipe_batch = os.environ.get("SENSIBLAW_STREAM_PIPE_BATCH_SIZE")
    try:
        if args.pipe_batch_size is None:
            os.environ.pop("SENSIBLAW_STREAM_PIPE_BATCH_SIZE", None)
        else:
            os.environ["SENSIBLAW_STREAM_PIPE_BATCH_SIZE"] = str(args.pipe_batch_size)
        receipt = run_direct_gate_a_benchmark(
            database_url=args.database_url,
            run_ref=run_ref,
            document_ref=args.document_ref,
            canonical_text=text,
            parser_contract_ref=args.parser_contract_ref,
            artifact_root=args.artifact_root,
            policy=policy,
        )
    finally:
        if prior_pipe_batch is None:
            os.environ.pop("SENSIBLAW_STREAM_PIPE_BATCH_SIZE", None)
        else:
            os.environ["SENSIBLAW_STREAM_PIPE_BATCH_SIZE"] = prior_pipe_batch

    payload: dict[str, object] = asdict(receipt)
    payload["schedule_authority_parity_preflight"] = (
        asdict(schedule_parity)
        if schedule_parity is not None
        else {"authority_equal": True, "mode": "coarse_schedule_no_refinement"}
    )

    partition_counts = _partition_sentence_counts(
        args.database_url,
        run_ref=run_ref,
        document_ref=args.document_ref,
    )
    if partition_counts and sum(partition_counts) == receipt.sentence_count:
        overlap = partition_aware_eof_overlap(
            partition_sentence_counts=partition_counts,
            semantic_sentences_at_parser_eof=receipt.semantic_sentences_at_parser_eof,
        )
        payload.update(asdict(overlap))
        payload["raw_eof_fraction_is_overlap_evidence"] = (
            overlap.raw_eof_fraction_is_overlap_evidence
        )
    else:
        payload["partition_sentence_counts"] = partition_counts
        payload["partition_aware_overlap_status"] = "unavailable_or_repair_partitioned"

    structural_intervals = _structural_partition_intervals(
        args.database_url,
        run_ref=run_ref,
        document_ref=args.document_ref,
    )
    if structural_intervals:
        payload["structural_partition_geometry"] = asdict(
            partition_geometry(structural_intervals)
        )
    physical_context_chars = _physical_parser_context_chars(
        args.database_url,
        run_ref=run_ref,
        document_ref=args.document_ref,
    )
    payload["physical_parser_context_chars"] = physical_context_chars
    payload["physical_parser_context_work_ratio"] = physical_context_chars / max(
        1, len(text)
    )
    payload["parser_policy"] = {
        "target_chars": policy.target_chars,
        "requested_target_partitions": args.target_partitions,
        "context_chars": policy.context_chars,
        "lease_batch_size": policy.batch_size,
        "pipe_batch_size": args.pipe_batch_size or policy.batch_size,
        "lease_seconds": policy.lease_seconds,
        "partition_refinement_mode": (
            "approximate_target_count"
            if args.target_partitions is not None
            else "historical"
        ),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--parser-contract-ref", required=True)
    parser.add_argument("--document-ref", default="gate-a-direct-benchmark")
    parser.add_argument("--run-ref")
    parser.add_argument("--artifact-root", type=Path, default=Path(".artifacts/gate-a"))
    parser.add_argument("--target-chars", type=int, default=_COARSE_TARGET_CHARS)
    parser.add_argument("--target-partitions", type=int)
    parser.add_argument("--context-chars", type=int, default=2_048)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--pipe-batch-size", type=int)
    parser.add_argument("--lease-seconds", type=int, default=180)
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if args.pipe_batch_size is not None and args.pipe_batch_size < 1:
        parser.error("--pipe-batch-size must be positive")
    if args.target_partitions is not None and args.target_partitions < 1:
        parser.error("--target-partitions must be positive")

    args.artifact_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] | None = None
    try:
        payload = _run(args)
        archive = args.artifact_root.parent / f"{args.artifact_root.name}.tar.xz"
        payload["diagnostic_bundle"] = str(archive)
        write_json_receipt(
            args.artifact_root,
            payload,
            filename="receipt-v2.json",
        )
        print(json.dumps(payload, sort_keys=True, indent=2))
        return 0
    except BaseException as error:
        failure = {
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "text_file": str(args.text_file),
            "target_chars": args.target_chars,
            "target_partitions": args.target_partitions,
            "context_chars": args.context_chars,
            "batch_size": args.batch_size,
            "pipe_batch_size": args.pipe_batch_size,
        }
        write_json_receipt(
            args.artifact_root,
            failure,
            filename="failure-v2.json",
        )
        raise
    finally:
        archive = bundle_artifact_directory(args.artifact_root)


if __name__ == "__main__":
    raise SystemExit(main())
