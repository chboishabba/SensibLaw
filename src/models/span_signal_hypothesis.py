from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SpanSignalHypothesis:
    """Pre-ontological signal span derived from canonical text."""

    span_start: int
    span_end: int
    span_source: str
    signal_type: str
    extractor: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    span_id: Optional[int] = None

    def to_record(self) -> Dict[str, Any]:
        """Serialize to a record suitable for storage."""

        return {
            "span_start": self.span_start,
            "span_end": self.span_end,
            "span_source": self.span_source,
            "span_id": self.span_id,
            "signal_type": self.signal_type,
            "extractor": self.extractor,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }


__all__ = ["SpanSignalHypothesis"]
