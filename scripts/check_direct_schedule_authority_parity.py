#!/usr/bin/env python3
"""Fail closed if a physical parser schedule changes direct semantic authority."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.runtime.parser_schedule_parity_preflight import run_schedule_parity_preflight
from src.runtime.streaming_partition_refinement import target_chars_for_partition_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--coarse-target-chars", type=int, default=32_768)
    parser.add_argument("--candidate-target-chars", type=int)
    parser.add_argument("--candidate-target-partitions", type=int)
    parser.add_argument("--context-chars", type=int, default=2_048)
    args = parser.parse_args()

    if (args.candidate_target_chars is None) == (
        args.candidate_target_partitions is None
    ):
        parser.error(
            "provide exactly one of --candidate-target-chars or "
            "--candidate-target-partitions"
        )

    text = args.text_file.read_text(encoding="utf-8")
    candidate_target_chars = args.candidate_target_chars
    if candidate_target_chars is None:
        candidate_target_chars = target_chars_for_partition_count(
            source_chars=len(text),
            target_partitions=args.candidate_target_partitions,
        )

    receipt = run_schedule_parity_preflight(
        text,
        coarse_target_chars=args.coarse_target_chars,
        candidate_target_chars=candidate_target_chars,
        context_chars=args.context_chars,
    )
    print(json.dumps(asdict(receipt), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
