"""Consumer-stable parity for alternative physical parser schedules.

This deliberately reuses ``direct_sentence_parity`` rather than inventing a
scheduler-specific fingerprint.  Physical partitioning is admissible only when
all schedules project to the same ordered source-coordinate sentence observations
in the same surrogate-independent object/factor/demand language used by G3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.pnf.direct_sentence_compiler import compile_packed_sentence
from src.pnf.direct_sentence_parity import (
    StableSentenceObservation,
    observe_sentence_closure,
)
from src.pnf.packed_sentence_fibre import PackedSentenceFibre


@dataclass(frozen=True, slots=True)
class StableOwnedSentenceObservation:
    start_char: int
    end_char: int
    sentence_digest: bytes
    semantic: StableSentenceObservation


def observe_owned_fibre(fibre: PackedSentenceFibre) -> StableOwnedSentenceObservation:
    """Compile one owned fibre and erase all local/database surrogate addresses."""

    receipt = compile_packed_sentence(fibre=fibre)
    evidence_by_address = dict(receipt.source_evidence_ids)
    symbol_by_id = {
        int(symbol_id): (kind, text)
        for kind, text, symbol_id in receipt.symbol_ids
    }
    semantic = observe_sentence_closure(
        receipt.closure,
        evidence_by_address=evidence_by_address,
        symbol_by_id=symbol_by_id,
    )
    return StableOwnedSentenceObservation(
        start_char=fibre.start_char,
        end_char=fibre.end_char,
        sentence_digest=bytes(fibre.sentence_digest),
        semantic=semantic,
    )


def observe_owned_schedule(
    fibres: Iterable[PackedSentenceFibre],
) -> tuple[StableOwnedSentenceObservation, ...]:
    """Return the canonical ordered semantic observation for one physical schedule."""

    observed = tuple(observe_owned_fibre(fibre) for fibre in fibres)
    ordered = tuple(
        sorted(
            observed,
            key=lambda row: (row.start_char, row.end_char, row.sentence_digest),
        )
    )
    anchors = [(row.start_char, row.end_char) for row in ordered]
    if len(set(anchors)) != len(anchors):
        raise RuntimeError("physical parser schedule projected duplicate owned sentence anchors")
    return ordered


def assert_schedule_authority_parity(
    coarse: tuple[StableOwnedSentenceObservation, ...],
    candidate: tuple[StableOwnedSentenceObservation, ...],
) -> None:
    """Fail closed before timing interpretation if a physical schedule changes semantics."""

    if coarse != candidate:
        raise RuntimeError(
            "parser schedule authority parity mismatch; performance comparison is forbidden"
        )


__all__ = [
    "StableOwnedSentenceObservation",
    "assert_schedule_authority_parity",
    "observe_owned_fibre",
    "observe_owned_schedule",
]
