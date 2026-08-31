"""DB-free authority-parity preflight for physical parser schedules."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.nlp.spacy_adapter import get_streaming_nlp
from src.pnf.packed_sentence_fibre import pack_spacy_partition
from src.pnf.parser_schedule_parity import (
    assert_schedule_authority_parity,
    observe_owned_schedule,
)
from src.storage.postgres.spacy_parser_model import (
    ParserStreamingPolicy,
    build_structural_partitions,
    byte_offsets,
)


@dataclass(frozen=True, slots=True)
class ScheduleParityPreflightReceipt:
    coarse_partition_count: int
    candidate_partition_count: int
    coarse_owned_sentence_count: int
    candidate_owned_sentence_count: int
    coarse_completed_boundaries: int
    candidate_completed_boundaries: int
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


def _parse_one(pipeline, text: str, partition):
    ((doc, returned),) = tuple(
        pipeline.pipe(
            ((text[partition.context_start_char : partition.context_end_char], partition),),
            as_tuples=True,
            batch_size=1,
            n_process=1,
        )
    )
    return doc, returned


def _completion_partition(text: str, partition, *, start: int, end: int, context_chars: int):
    ordinary = max(1, int(context_chars))
    radius = ordinary * 4
    context_start = max(0, int(start) - radius)
    context_end = min(len(text), int(end) + radius)
    offsets = byte_offsets(text, (context_start, context_end))
    return replace(
        partition,
        context_start_char=context_start,
        context_end_char=context_end,
        context_start_byte=offsets[context_start],
        context_end_byte=offsets[context_end],
    )


def _owned_fibres(pipeline, text: str, partitions, *, context_chars: int):
    fibres = []
    completed_boundaries = 0
    for partition in partitions:
        doc, partition = _parse_one(pipeline, text, partition)
        packed = pack_spacy_partition(
            partition,
            doc,
            context_reaches_source_end=(partition.context_end_char == len(text)),
        )
        fibres.extend(packed.sentences)
        owned_starts = {fibre.start_char for fibre in packed.sentences}

        # Only a start-owned observation withheld at the parser context edge
        # requires completion. Fully observed crossings may remain explicit
        # validation obligations without changing semantic authority.
        for start, end, _start_byte, _end_byte in packed.boundary_obligations:
            if not (partition.owner_start_char <= start < partition.owner_end_char):
                continue
            if start in owned_starts:
                continue
            completion_partition = _completion_partition(
                text,
                partition,
                start=start,
                end=end,
                context_chars=context_chars,
            )
            completion_doc, completion_partition = _parse_one(
                pipeline,
                text,
                completion_partition,
            )
            completed = pack_spacy_partition(
                completion_partition,
                completion_doc,
                context_reaches_source_end=(
                    completion_partition.context_end_char == len(text)
                ),
            )
            candidates = tuple(
                fibre for fibre in completed.sentences if fibre.start_char == start
            )
            if len(candidates) != 1:
                raise RuntimeError(
                    "schedule parity boundary completion did not yield exactly one "
                    f"owned sentence at source anchor {start}"
                )
            fibres.append(candidates[0])
            completed_boundaries += 1
    return tuple(fibres), completed_boundaries


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
    coarse_fibres, coarse_completed = _owned_fibres(
        pipeline,
        text,
        coarse,
        context_chars=context_chars,
    )
    candidate_fibres, candidate_completed = _owned_fibres(
        pipeline,
        text,
        candidate,
        context_chars=context_chars,
    )
    coarse_observation = observe_owned_schedule(coarse_fibres)
    candidate_observation = observe_owned_schedule(candidate_fibres)
    equal = coarse_observation == candidate_observation
    receipt = ScheduleParityPreflightReceipt(
        coarse_partition_count=len(coarse),
        candidate_partition_count=len(candidate),
        coarse_owned_sentence_count=len(coarse_observation),
        candidate_owned_sentence_count=len(candidate_observation),
        coarse_completed_boundaries=coarse_completed,
        candidate_completed_boundaries=candidate_completed,
        authority_equal=equal,
    )
    assert_schedule_authority_parity(coarse_observation, candidate_observation)
    return receipt


__all__ = ["ScheduleParityPreflightReceipt", "run_schedule_parity_preflight"]
