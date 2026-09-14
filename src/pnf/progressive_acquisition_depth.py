"""Residual-driven progressive acquisition over cheap observation surfaces.

Search-result metadata, abstracts/snippets and full sources are separate source
observations.  Moving deeper is authorised only while a live consumer residual
remains and the acquisition policy has budget.  Depth never promotes truth by
itself; high-stakes payment remains a reviewed, source-role-sensitive step.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from src.pnf.federated_zos_acquisition import AcquisitionPolicy, SourceClass


class AcquisitionDepth(IntEnum):
    SEARCH_RESULT = 1
    ABSTRACT = 2
    FULL_SOURCE = 3


@dataclass(frozen=True, slots=True)
class AcquisitionObservation:
    source_ref: str
    source_class: SourceClass
    depth: AcquisitionDepth
    source_identity_verified: bool
    exact_source_span_available: bool
    semantic_authority: bool = False
    claim_truth_promoted: bool = False
    review_required: bool = True


@dataclass(frozen=True, slots=True)
class DepthDecision:
    should_acquire: bool
    next_depth: AcquisitionDepth | None
    reason: str
    creates_evidence_payment: bool = False
    creates_claim_truth: bool = False


def choose_next_depth(
    *,
    residual_level: str,
    current_depth: AcquisitionDepth,
    policy: AcquisitionPolicy,
    source_class: SourceClass,
    network_requests_used: int,
) -> DepthDecision:
    """Choose the next observation depth without conflating depth with evidence.

    A paid/exact residual does no work.  Unsupported source classes and exhausted
    budgets stop cleanly.  Otherwise progression is monotone:
    search-result -> abstract -> full source.
    """

    level = residual_level.strip().lower()
    if level == "exact":
        return DepthDecision(False, None, "residual-already-paid")
    if level not in {"partial", "no_typed_meet", "contradiction"}:
        raise ValueError(f"unsupported residual level: {residual_level!r}")
    if source_class not in policy.allowed_source_classes:
        return DepthDecision(False, None, "source-class-not-admitted")
    if network_requests_used >= policy.network_budget:
        return DepthDecision(False, None, "network-budget-exhausted")
    if int(current_depth) >= min(int(AcquisitionDepth.FULL_SOURCE), policy.max_depth):
        return DepthDecision(False, None, "maximum-depth-reached")

    next_depth = AcquisitionDepth(int(current_depth) + 1)
    return DepthDecision(True, next_depth, "live-residual-progressive-deepening")


def primary_authority_payment_eligible(
    policy: AcquisitionPolicy,
    observation: AcquisitionObservation,
) -> bool:
    """Return only structural eligibility for later reviewed evidence payment.

    Strict legal consumers require an identified full primary-authority source
    with an exact source span.  This function does not perform the review or
    append a payment receipt.
    """

    if policy.consumer_ref != "legal-proof-graph":
        return False
    return (
        observation.source_class is SourceClass.PRIMARY_AUTHORITY
        and observation.depth is AcquisitionDepth.FULL_SOURCE
        and observation.source_identity_verified
        and observation.exact_source_span_available
        and observation.review_required
        and not observation.semantic_authority
        and not observation.claim_truth_promoted
    )


__all__ = [
    "AcquisitionDepth",
    "AcquisitionObservation",
    "DepthDecision",
    "choose_next_depth",
    "primary_authority_payment_eligible",
]
