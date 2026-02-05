from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .span_role_hypothesis import SpanRoleHypothesis


@dataclass(frozen=True)
class PromotionCandidate:
    """Candidate ontology promotion derived from a span hypothesis."""

    normalized_label: str
    gate_id: str
    hypothesis: SpanRoleHypothesis


@dataclass(frozen=True)
class PromotionReceipt:
    """Record of a promotion decision for a span hypothesis."""

    gate_id: str
    status: str
    reason: str
    hypothesis: Dict[str, Any]
    evidence: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


__all__ = ["PromotionCandidate", "PromotionReceipt"]
