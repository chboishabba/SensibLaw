"""Exactly-once authority projection for overlapping parser observations.

Physical parser partitions may overlap through bilateral context, repairs, retries,
or future finer streaming schedules.  Observation is not semantic authority.
Every sentence candidate is assigned to the unique structural owner interval that
contains its canonical start coordinate.  Context and repair observations are
strictly evidence-only.

Formal companion:
``DASHI/Cognition/PNF/ExactlyOnceParserAuthorityProjectionExact.agda``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PartitionAuthorityView(Protocol):
    partition_kind: str
    owner_start_char: int
    owner_end_char: int


class ObservationRole(str, Enum):
    STRUCTURAL_OWNER = "structural_owner"
    STRUCTURAL_CONTEXT = "structural_context"
    BOUNDARY_REPAIR = "boundary_repair"
    OTHER_EVIDENCE = "other_evidence"


@dataclass(frozen=True, slots=True)
class SentenceAuthorityProjection:
    role: ObservationRole
    authority_bearing: bool
    source_anchor: int


def project_sentence_authority(
    partition: PartitionAuthorityView,
    *,
    start_char: int,
) -> SentenceAuthorityProjection:
    """Classify one parsed sentence observation before semantic compilation.

    Sentence start is the canonical source anchor. Structural owner intervals are
    disjoint, so exactly one structural partition can own a given anchor. Repair
    and context observations never acquire authority merely because their parser
    context contains the same sentence.
    """

    start = int(start_char)
    kind = str(partition.partition_kind)
    if kind == "structural":
        owns = int(partition.owner_start_char) <= start < int(partition.owner_end_char)
        return SentenceAuthorityProjection(
            role=(
                ObservationRole.STRUCTURAL_OWNER
                if owns
                else ObservationRole.STRUCTURAL_CONTEXT
            ),
            authority_bearing=owns,
            source_anchor=start,
        )
    if kind == "boundary_repair":
        return SentenceAuthorityProjection(
            role=ObservationRole.BOUNDARY_REPAIR,
            authority_bearing=False,
            source_anchor=start,
        )
    return SentenceAuthorityProjection(
        role=ObservationRole.OTHER_EVIDENCE,
        authority_bearing=False,
        source_anchor=start,
    )


def assert_authority_projection_is_valid(
    partition: PartitionAuthorityView,
    *,
    start_char: int,
    projection: SentenceAuthorityProjection,
) -> None:
    """Fail closed if a physical non-owner is ever promoted to authority."""

    expected = project_sentence_authority(partition, start_char=start_char)
    if projection != expected:
        raise RuntimeError("parser authority projection diverged from canonical owner law")
    if projection.authority_bearing and projection.role is not ObservationRole.STRUCTURAL_OWNER:
        raise RuntimeError("non-structural parser observation attempted to mint authority")


__all__ = [
    "ObservationRole",
    "PartitionAuthorityView",
    "SentenceAuthorityProjection",
    "assert_authority_projection_is_valid",
    "project_sentence_authority",
]
