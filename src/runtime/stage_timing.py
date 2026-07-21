"""Per-document nested timing and reduction-efficiency instrumentation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import monotonic_ns
from typing import Any, Iterator, Mapping

from src.policy.carriers.canonical import canonical_sha256


STAGE_TIMING_SCHEMA_VERSION = "sl.semantic_stage_timing.v0_1"
STAGE_TIMING_LEDGER_SCHEMA_VERSION = "sl.semantic_stage_timing_ledger.v0_1"


@dataclass(frozen=True)
class StageTiming:
    document_ref: str
    stage: str
    ordinal: int
    elapsed_ms: int
    backend_ref: str | None = None
    input_nodes: int | None = None
    output_nodes: int | None = None
    input_edges: int | None = None
    output_edges: int | None = None
    proposals_generated: int | None = None
    duplicates_collapsed: int | None = None
    invalid_rejected: int | None = None
    alternatives_retained: int | None = None
    residuals_emitted: int | None = None
    tokens_processed: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def timing_ref(self) -> str:
        return "semantic-stage-timing:" + canonical_sha256(self.to_dict(include_ref=False))

    @property
    def tokens_per_second(self) -> float | None:
        if self.tokens_processed is None or self.elapsed_ms <= 0:
            return None
        return self.tokens_processed / (self.elapsed_ms / 1000.0)

    @property
    def reduction_ratio(self) -> float | None:
        if self.input_edges is None or self.output_edges is None or self.input_edges <= 0:
            return None
        return max(0.0, (self.input_edges - self.output_edges) / self.input_edges)

    @property
    def reduction_efficiency_edges_per_second(self) -> float | None:
        if self.input_edges is None or self.output_edges is None or self.elapsed_ms <= 0:
            return None
        return (self.input_edges - self.output_edges) / (self.elapsed_ms / 1000.0)

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": STAGE_TIMING_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "stage": self.stage,
            "ordinal": self.ordinal,
            "elapsed_ms": self.elapsed_ms,
            "details": dict(self.details),
        }
        optional = {
            "backend_ref": self.backend_ref,
            "input_nodes": self.input_nodes,
            "output_nodes": self.output_nodes,
            "input_edges": self.input_edges,
            "output_edges": self.output_edges,
            "proposals_generated": self.proposals_generated,
            "duplicates_collapsed": self.duplicates_collapsed,
            "invalid_rejected": self.invalid_rejected,
            "alternatives_retained": self.alternatives_retained,
            "residuals_emitted": self.residuals_emitted,
            "tokens_processed": self.tokens_processed,
            "tokens_per_second": self.tokens_per_second,
            "reduction_ratio": self.reduction_ratio,
            "reduction_efficiency_edges_per_second": self.reduction_efficiency_edges_per_second,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        if include_ref:
            payload["timing_ref"] = self.timing_ref
        return payload


@dataclass
class StageHandle:
    ledger: "StageTimingLedger"
    stage: str
    backend_ref: str | None
    details: dict[str, Any]
    _started_ns: int = field(default_factory=monotonic_ns)
    _metrics: dict[str, Any] = field(default_factory=dict)

    def record(self, **metrics: Any) -> None:
        self._metrics.update({key: value for key, value in metrics.items() if value is not None})

    def finish(self) -> StageTiming:
        elapsed_ms = max(0, (monotonic_ns() - self._started_ns) // 1_000_000)
        timing = StageTiming(
            document_ref=self.ledger.document_ref,
            stage=self.stage,
            ordinal=len(self.ledger.timings),
            elapsed_ms=elapsed_ms,
            backend_ref=self.backend_ref,
            input_nodes=self._metrics.get("input_nodes"),
            output_nodes=self._metrics.get("output_nodes"),
            input_edges=self._metrics.get("input_edges"),
            output_edges=self._metrics.get("output_edges"),
            proposals_generated=self._metrics.get("proposals_generated"),
            duplicates_collapsed=self._metrics.get("duplicates_collapsed"),
            invalid_rejected=self._metrics.get("invalid_rejected"),
            alternatives_retained=self._metrics.get("alternatives_retained"),
            residuals_emitted=self._metrics.get("residuals_emitted"),
            tokens_processed=self._metrics.get("tokens_processed"),
            details={**self.details, **dict(self._metrics.get("details") or {})},
        )
        self.ledger.timings.append(timing)
        return timing


@dataclass
class StageTimingLedger:
    document_ref: str
    timings: list[StageTiming] = field(default_factory=list)

    @contextmanager
    def stage(
        self,
        stage: str,
        *,
        backend_ref: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> Iterator[StageHandle]:
        handle = StageHandle(
            ledger=self,
            stage=stage,
            backend_ref=backend_ref,
            details=dict(details or {}),
        )
        try:
            yield handle
        finally:
            handle.finish()

    @property
    def ledger_ref(self) -> str:
        return "semantic-stage-ledger:" + canonical_sha256(self.to_dict(include_ref=False))

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        stage_totals: dict[str, int] = {}
        for timing in self.timings:
            stage_totals[timing.stage] = stage_totals.get(timing.stage, 0) + timing.elapsed_ms
        payload = {
            "schema_version": STAGE_TIMING_LEDGER_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "stage_totals_ms": {key: stage_totals[key] for key in sorted(stage_totals)},
            "timings": [row.to_dict() for row in self.timings],
        }
        if include_ref:
            payload["ledger_ref"] = self.ledger_ref
        return payload


__all__ = [
    "STAGE_TIMING_LEDGER_SCHEMA_VERSION",
    "STAGE_TIMING_SCHEMA_VERSION",
    "StageHandle",
    "StageTiming",
    "StageTimingLedger",
]
