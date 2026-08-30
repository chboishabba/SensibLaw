#!/usr/bin/env python3
"""Fail closed if a physical parser schedule changes direct semantic authority."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from src.nlp.spacy_adapter import get_streaming_nlp
from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.pnf.parser_schedule_parity import (
    assert_schedule_authority_parity,
    observe_owned_schedule,
)
from src.runtime.streaming_partition_refinement import target_chars_for_partition_count
from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    build_structural_partitions,
)


@dataclass(frozen=True, slots=True)
class ScheduleParityPreflightReceipt:
    coarse_partition_count: int
    candidate_partition_count: int
    coarse_owned_sentence_count: int
    candidate_owned_sentence_count: int
    authority_equal: bool


def _build_partitions(
    text: str,
    *,
    target_chars: int,
    context_chars: int,
    label: str,
):
    policy = ParserStreamingPolicy(
        target_chars=target_chars,
        context_chars=context_chars,
        batch_size=4,
        lease_seconds=180,
        cache_docbin=False,
    )
    return build_structural_partitions(
        run_ref="schedule-parity-preflight",
        document_ref="schedule-parity-document",
        source_ref="schedule-parity-source",
        source_locator=f"memory:{label}",
        parser_contract_ref="schedule-parity-preflight:v1",
        canonical_text=text,
        policy=policy,
    )


def _owned_fibres(pipeline, text: str, partitions):
    inputs = tuple(
        (
            text[partition.context_start_char : partition.context_end_char],
            partition,
        )
        for partition in partitions
    )
    fibres = []
    for doc, partition in pipeline.pipe(
        inputs,
        as_tuples=True,
        batch_size=1,
        n_process=1,
    ):
        fibres.extend(pack_spacy_partition(partition, doc).sentences)
    return tuple(fibres)


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

    coarse = _build_partitions(
        text,
        target_chars=args.coarse_target_chars,
        context_chars=args.context_chars,
        label="coarse",
    )
    candidate = _build_partitions(
        text,
        target_chars=candidate_target_chars,
        context_chars=args.context_chars,
        label="candidate",
    )

    pipeline = get_streaming_nlp()
    coarse_fibres = _owned_fibres(pipeline, text, coarse)
    candidate_fibres = _owned_fibres(pipeline, text, candidate)
    coarse_observation = observe_owned_schedule(coarse_fibres)
    candidate_observation = observe_owned_schedule(candidate_fibres)

    equal = coarse_observation == candidate_observation
    receipt = ScheduleParityPreflightReceipt(
        coarse_partition_count=len(coarse),
        candidate_partition_count=len(candidate),
        coarse_owned_sentence_count=len(coarse_observation),
        candidate_owned_sentence_count=len(candidate_observation),
        authority_equal=equal,
    )
    print(json.dumps(asdict(receipt), sort_keys=True, indent=2))
    assert_schedule_authority_parity(coarse_observation, candidate_observation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
