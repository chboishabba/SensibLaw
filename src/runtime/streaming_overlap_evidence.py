"""Partition-aware evidence for parser/semantic streaming overlap.

A high fraction of semantic work completed at parser EOF is not, by itself,
evidence of useful overlap.  If the final parser partition is tiny, a completely
serial partition pipeline can already be almost entirely complete when parser
EOF occurs.

This module removes that geometric baseline.  It is diagnostic only; it does
not alter parser partitioning or semantic authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PartitionAwareEOFOverlap:
    """Explain EOF completion relative to the serial partition floor."""

    partition_sentence_counts: tuple[int, ...]
    total_semantic_sentences: int
    final_partition_sentences: int
    pre_final_partition_sentences: int
    semantic_sentences_at_parser_eof: int
    serial_eof_floor_fraction: float
    observed_eof_completion_fraction: float
    overlap_completion_gain_sentences: int
    overlap_completion_gain_fraction: float
    largest_partition_fraction: float
    final_partition_fraction: float

    @property
    def raw_eof_fraction_is_overlap_evidence(self) -> bool:
        """True only when EOF completion exceeds the serial partition floor."""

        return self.overlap_completion_gain_sentences > 0


def partition_aware_eof_overlap(
    *,
    partition_sentence_counts: Sequence[int],
    semantic_sentences_at_parser_eof: int,
) -> PartitionAwareEOFOverlap:
    """Return the EOF completion attributable to overlap beyond serial geometry.

    For ordered partition counts ``p_1, ..., p_n``, a serial parser-then-consume
    implementation can have all of ``p_1, ..., p_(n-1)`` semantically complete
    by the moment the parser finishes ``p_n``.  Therefore

        serial floor = sum(p_1..p_(n-1)) / sum(p_1..p_n)

    and only completion above that floor is evidence that semantic consumption
    materially overlapped parsing of the final partition.
    """

    counts = tuple(int(value) for value in partition_sentence_counts)
    if not counts:
        raise ValueError("partition sentence counts must be non-empty")
    if any(value < 0 for value in counts):
        raise ValueError("partition sentence counts must be non-negative")

    total = sum(counts)
    if total <= 0:
        raise ValueError("partition sentence counts must contain semantic work")

    completed = int(semantic_sentences_at_parser_eof)
    if not 0 <= completed <= total:
        raise ValueError("semantic EOF completion lies outside total sentence count")

    final_count = counts[-1]
    pre_final = total - final_count
    gain = max(0, completed - pre_final)
    return PartitionAwareEOFOverlap(
        partition_sentence_counts=counts,
        total_semantic_sentences=total,
        final_partition_sentences=final_count,
        pre_final_partition_sentences=pre_final,
        semantic_sentences_at_parser_eof=completed,
        serial_eof_floor_fraction=pre_final / total,
        observed_eof_completion_fraction=completed / total,
        overlap_completion_gain_sentences=gain,
        overlap_completion_gain_fraction=gain / total,
        largest_partition_fraction=max(counts) / total,
        final_partition_fraction=final_count / total,
    )


__all__ = ["PartitionAwareEOFOverlap", "partition_aware_eof_overlap"]
