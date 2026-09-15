"""Thin SensibLaw-owned Mabo profile for the generic SLR recurrence.

This module owns only the legal-consumer -> existing SLR coordinate mapping.
It does not execute search, encode SLRC bytes, parse sources, review evidence,
or promote legal truth.  Production recurrence execution remains in the Rust
SLR/DASHI pipeline; this Python surface is a reference/golden contract for the
SensibLaw-owned legal mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MaboResidualState(str, Enum):
    EXACT = "exact"
    PARTIAL = "partial"
    NO_TYPED_MEET = "no_typed_meet"
    CONTRADICTION = "contradiction"


class EvidenceNeed(str, Enum):
    SOURCE_IDENTITY = "source-identity"
    SAME_OBJECT = "same-object"
    AUTHORITY = "authority"


@dataclass(frozen=True, slots=True)
class SLRRequirementProjection:
    requirement_id: str
    need: EvidenceNeed
    scope: str = "any"


@dataclass(frozen=True, slots=True)
class MaboSLRProfile:
    consumer_id: str
    surface_id: str
    residual: MaboResidualState
    requirements: tuple[SLRRequirementProjection, ...]
    search_reason: str
    evidence_search_authorised: bool
    slrc_version: int = 2
    candidate_only: bool = True
    semantic_promotion: bool = False
    world_truth_claimed: bool = False
    creates_legal_conclusion: bool = False
    creates_evidence_payment: bool = False
    requires_review_before_payment: bool = True
    python_is_production_slr_semantic_runtime: bool = False


def _live_requirements(surface_id: str) -> tuple[SLRRequirementProjection, ...]:
    return (
        SLRRequirementProjection(
            requirement_id=f"{surface_id}:source-identity",
            need=EvidenceNeed.SOURCE_IDENTITY,
        ),
        SLRRequirementProjection(
            requirement_id=f"{surface_id}:same-object",
            need=EvidenceNeed.SAME_OBJECT,
        ),
        SLRRequirementProjection(
            requirement_id=f"{surface_id}:authority",
            need=EvidenceNeed.AUTHORITY,
        ),
    )


def build_mabo_slr_profile(
    *,
    consumer_id: str,
    surface_id: str,
    residual: MaboResidualState,
) -> MaboSLRProfile:
    """Translate a reviewed Mabo residual into existing SLRC-v2 coordinates."""

    if not consumer_id:
        raise ValueError("consumer_id must be non-empty")
    if not surface_id:
        raise ValueError("surface_id must be non-empty")

    if residual is MaboResidualState.EXACT:
        return MaboSLRProfile(
            consumer_id=consumer_id,
            surface_id=surface_id,
            residual=residual,
            requirements=(),
            search_reason="typed coordinate already shared; no new acquisition work",
            evidence_search_authorised=False,
        )

    reason = {
        MaboResidualState.PARTIAL:
            "typed legal coordinate is incompletely supported; acquire missing source/authority coordinates",
        MaboResidualState.NO_TYPED_MEET:
            "sources lack a reviewed typed meet; acquire identity/same-object/authority discriminators",
        MaboResidualState.CONTRADICTION:
            "reviewed typed conflict remains; acquire source identity, same-object and authority evidence",
    }[residual]

    return MaboSLRProfile(
        consumer_id=consumer_id,
        surface_id=surface_id,
        residual=residual,
        requirements=_live_requirements(surface_id),
        search_reason=reason,
        evidence_search_authorised=True,
    )


__all__ = [
    "EvidenceNeed",
    "MaboResidualState",
    "MaboSLRProfile",
    "SLRRequirementProjection",
    "build_mabo_slr_profile",
]
