from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SpanRoleHypothesis:
    """Pre-ontological span hypothesis derived from canonical text."""

    span_start: int
    span_end: int
    span_source: str
    span_id: Optional[int] = None
    role_hypothesis: Optional[str] = None
    extractor: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_record(self) -> Dict[str, Any]:
        """Serialize to a record suitable for storage."""

        return {
            "span_start": self.span_start,
            "span_end": self.span_end,
            "span_source": self.span_source,
            "span_id": self.span_id,
            "role_hypothesis": self.role_hypothesis,
            "extractor": self.extractor,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }

    def to_lexical_hint_record(self) -> Dict[str, Any]:
        """Serialize regex/scan output as a non-semantic lexical hint."""

        record = self.to_record()
        record.update(
            {
                "schema": "lexical_hint_v1",
                "hint_kind": "span_role",
                "pnf_candidates": [],
                "non_authoritative": True,
                "bounded": True,
            }
        )
        return record


__all__ = ["SpanRoleHypothesis"]
