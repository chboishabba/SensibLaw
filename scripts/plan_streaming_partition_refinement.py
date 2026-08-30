#!/usr/bin/env python3
"""Plan physical streaming partition probes without running spaCy or PostgreSQL."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.runtime.streaming_partition_refinement import (
    partition_geometry,
    target_chars_for_partition_count,
)
from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    build_structural_partitions,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument(
        "--target-partitions",
        type=int,
        action="append",
        required=True,
        help="repeat to compare several approximate structural partition counts",
    )
    parser.add_argument("--context-chars", type=int, default=2_048)
    args = parser.parse_args()

    text = args.text_file.read_text(encoding="utf-8")
    rows: list[dict[str, object]] = []
    for requested in args.target_partitions:
        target_chars = target_chars_for_partition_count(
            source_chars=len(text),
            target_partitions=requested,
        )
        policy = ParserStreamingPolicy(
            target_chars=target_chars,
            context_chars=args.context_chars,
        )
        partitions = build_structural_partitions(
            run_ref="partition-refinement-plan",
            document_ref="partition-refinement-plan",
            source_ref="parser-source:partition-refinement-plan",
            source_locator="<plan-only>",
            parser_contract_ref="partition-refinement-plan",
            canonical_text=text,
            policy=policy,
        )
        geometry = partition_geometry(
            (
                partition.owner_start_char,
                partition.owner_end_char,
                partition.context_start_char,
                partition.context_end_char,
            )
            for partition in partitions
        )
        rows.append(
            {
                "requested_target_partitions": requested,
                "target_chars": target_chars,
                "context_chars": args.context_chars,
                "owner_sizes": [
                    partition.owner_end_char - partition.owner_start_char
                    for partition in partitions
                ],
                **asdict(geometry),
            }
        )

    print(json.dumps({"source_chars": len(text), "plans": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
