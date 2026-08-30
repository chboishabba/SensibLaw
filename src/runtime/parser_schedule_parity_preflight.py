"""DB-free authority-parity preflight for physical parser schedules."""

from __future__ import annotations

from dataclasses import dataclass

from src.nlp.spacy_adapter import get_streaming_nlp
from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.pnf.parser_schedule_parity import (
    assert_schedule_authority_parity,
    observe_owned_schedule,
)
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


def _partitions(text: str, *, target_chars: int, context_chars: int, label: str):
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
        (text[p.context_start_char : p.context_end_char], p) for p in partitions
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


def run_schedule_parity_preflight(
    text: str,
    *,
    coarse_target_chars: int,
    candidate_target_chars: int,
    context_chars: int,
) -> ScheduleParityPreflightReceipt:
    """Fail closed unless coarse and candidate schedules have identical authority."""

    if not text:
        raise ValueError("schedule parity preflight requires non-empty text")
    coarse = _partitions(
        text,
        target_chars=coarse_target_chars,
        context_chars=context_chars,
        label="coarse",
    )
    candidate = _partitions(
        text,
        target_chars=candidate_target_chars,
        context_chars=context_chars,
        label="candidate",
    )
    pipeline = get_streaming_nlp()
    coarse_observation = observe_owned_schedule(_owned_fibres(pipeline, text, coarse))
    candidate_observation = observe_owned_schedule(
        _owned_fibres(pipeline, text, candidate)
    )
    equal = coarse_observation == candidate_observation
    receipt = ScheduleParityPreflightReceipt(
        coarse_partition_count=len(coarse),
        candidate_partition_count=len(candidate),
        coarse_owned_sentence_count=len(coarse_observation),
        candidate_owned_sentence_count=len(candidate_observation),
        authority_equal=equal,
    )
    assert_schedule_authority_parity(coarse_observation, candidate_observation)
    return receipt


__all__ = ["ScheduleParityPreflightReceipt", "run_schedule_parity_preflight"]
