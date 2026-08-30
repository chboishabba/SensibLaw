"""Pure planning/receipt helpers for physical streaming partition refinement.

Partition refinement is an execution experiment only.  It may change physical
owner/context intervals, but it must not create a second semantic compiler or
change durable source ownership.  The formal companion is
``StreamingPhysicalPartitionRefinementExact.agda``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PartitionGeometryReceipt:
    partition_count: int
    source_owner_chars: int
    total_context_chars: int
    duplicated_context_chars: int
    context_duplication_fraction: float
    smallest_owner_chars: int
    largest_owner_chars: int
    owner_skew_ratio: float


def target_chars_for_partition_count(
    *,
    source_chars: int,
    target_partitions: int,
    min_target_chars: int = 1_024,
) -> int:
    """Choose a physical target size for an approximate partition-count probe.

    Structural boundaries remain authoritative for the actual cuts, so this is
    only a scheduling target rather than a promise of exactly ``target_partitions``.
    """

    if source_chars < 1:
        raise ValueError("source_chars must be positive")
    if target_partitions < 1:
        raise ValueError("target_partitions must be positive")
    if min_target_chars < 1:
        raise ValueError("min_target_chars must be positive")
    return max(min_target_chars, ceil(source_chars / target_partitions))


def partition_geometry(
    intervals: Iterable[tuple[int, int, int, int]],
) -> PartitionGeometryReceipt:
    """Measure owner balance and physical context duplication.

    Each row is ``(owner_start, owner_end, context_start, context_end)`` in
    canonical source coordinates.  Owned intervals are counted once; bilateral
    parser context is measured as physical duplicated work.
    """

    rows = tuple(intervals)
    if not rows:
        raise ValueError("partition geometry requires at least one interval")

    owner_sizes: list[int] = []
    context_sizes: list[int] = []
    for owner_start, owner_end, context_start, context_end in rows:
        owner_size = int(owner_end) - int(owner_start)
        context_size = int(context_end) - int(context_start)
        if owner_size <= 0:
            raise ValueError("partition owner interval must be non-empty")
        if context_size < owner_size:
            raise ValueError("partition context must contain its owner interval")
        owner_sizes.append(owner_size)
        context_sizes.append(context_size)

    source_owner_chars = sum(owner_sizes)
    total_context_chars = sum(context_sizes)
    duplicated_context_chars = total_context_chars - source_owner_chars
    smallest = min(owner_sizes)
    largest = max(owner_sizes)
    return PartitionGeometryReceipt(
        partition_count=len(rows),
        source_owner_chars=source_owner_chars,
        total_context_chars=total_context_chars,
        duplicated_context_chars=duplicated_context_chars,
        context_duplication_fraction=(
            duplicated_context_chars / source_owner_chars
            if source_owner_chars
            else 0.0
        ),
        smallest_owner_chars=smallest,
        largest_owner_chars=largest,
        owner_skew_ratio=largest / smallest,
    )


__all__ = [
    "PartitionGeometryReceipt",
    "partition_geometry",
    "target_chars_for_partition_count",
]
