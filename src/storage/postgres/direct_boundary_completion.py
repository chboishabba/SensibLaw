"""Evidence-only boundary completion for direct parser partitions.

The structural partition selected by the sentence start anchor remains the only
semantic owner.  A boundary-repair partition is only an evidence supplier: it
may widen parser context until a complete sentence observation is available,
but it never acquires a second semantic identity.

Formal companion:
``DASHI/Cognition/PNF/ParserBoundaryCompletionExact.agda``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.storage.postgres.spacy_parser_model import (
    ParserPartition,
    ParserStreamingPolicy,
    byte_offsets,
)
from src.storage.postgres.spacy_parser_store import _create_boundary_repair


def create_expanded_boundary_repair(
    cursor: Any,
    *,
    partition: ParserPartition,
    start_char: int,
    end_char: int,
    start_byte: int,
    end_byte: int,
    policy: ParserStreamingPolicy,
) -> tuple[str, str | None]:
    """Create the canonical repair, then widen its evidence context.

    Repair owner coordinates remain the suspected sentence interval because the
    durable scheduler already uses those coordinates for the obligation.  Only
    the parser context is widened.  Semantic authority remains with the source
    structural partition referenced by the obligation.
    """

    obligation_ref, repair_ref = _create_boundary_repair(
        cursor,
        partition=partition,
        start_char=start_char,
        end_char=end_char,
        start_byte=start_byte,
        end_byte=end_byte,
        policy=policy,
    )
    if repair_ref is None:
        return obligation_ref, None

    source_text = Path(partition.source_locator).read_text(encoding="utf-8")
    # The first repair gets four ordinary context widths.  Later repair depths
    # would double geometrically if the scheduler ever needs another attempt.
    ordinary = max(1, int(policy.context_chars))
    radius = ordinary * (4 << int(partition.repair_depth))
    context_start = max(0, int(start_char) - radius)
    context_end = min(len(source_text), int(end_char) + radius)
    byte_map = byte_offsets(source_text, (context_start, context_end))

    cursor.execute(
        """
        UPDATE execution.semantic_parser_partition
           SET context_start_char = %s,
               context_end_char = %s,
               context_start_byte = %s,
               context_end_byte = %s,
               updated_at = CURRENT_TIMESTAMP
         WHERE partition_ref = %s
           AND partition_kind = 'boundary_repair'
        """,
        (
            context_start,
            context_end,
            byte_map[context_start],
            byte_map[context_end],
            repair_ref,
        ),
    )
    return obligation_ref, repair_ref


__all__ = ["create_expanded_boundary_repair"]
