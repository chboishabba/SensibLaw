#!/usr/bin/env python3
"""Run the canonical packed-fibre Gate-A benchmark against a migrated database."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from uuid import uuid4

from src.runtime.streaming_overlap_evidence import partition_aware_eof_overlap
from src.storage.postgres.direct_gate_a_benchmark import run_direct_gate_a_benchmark
from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy, connect


def _partition_sentence_counts(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
) -> tuple[int, ...]:
    """Read structural partition sentence counts in canonical source order."""

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
                   AND p.partition_kind = 'structural'
                 ORDER BY p.owner_start_char, p.owner_end_char, p.partition_ref
                """,
                (run_ref, document_ref),
            )
            return tuple(int(row[0]) for row in cursor.fetchall())
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--parser-contract-ref", required=True)
    parser.add_argument("--document-ref", default="gate-a-direct-benchmark")
    parser.add_argument("--run-ref")
    parser.add_argument("--artifact-root", type=Path, default=Path(".artifacts/gate-a"))
    parser.add_argument("--target-chars", type=int, default=32_768)
    parser.add_argument("--context-chars", type=int, default=2_048)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lease-seconds", type=int, default=180)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    policy = ParserStreamingPolicy(
        target_chars=args.target_chars,
        context_chars=args.context_chars,
        batch_size=args.batch_size,
        lease_seconds=args.lease_seconds,
    )
    text = args.text_file.read_text(encoding="utf-8")
    run_ref = args.run_ref or f"gate-a-direct:{uuid4().hex}"
    receipt = run_direct_gate_a_benchmark(
        database_url=args.database_url,
        run_ref=run_ref,
        document_ref=args.document_ref,
        canonical_text=text,
        parser_contract_ref=args.parser_contract_ref,
        artifact_root=args.artifact_root,
        policy=policy,
    )

    payload = asdict(receipt)
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

    payload["parser_policy"] = {
        "target_chars": policy.target_chars,
        "context_chars": policy.context_chars,
        "batch_size": policy.batch_size,
        "lease_seconds": policy.lease_seconds,
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
