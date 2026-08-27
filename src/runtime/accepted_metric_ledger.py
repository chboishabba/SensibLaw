"""Fail-closed parser-relative acceptance timing for strict numeric PNF.

The numeric streaming runtime already emits direct monotonic occupancy and named
post-parser kernel measurements. This module normalizes that evidence without
inventing stage time by subtraction and makes missing attribution explicit.

A completed semantic run is not a performance acceptance result unless this
ledger can establish both sides of the parser-relative target.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any, Mapping

from src.runtime.delta_execution_timing import (
    DeltaExecutionTimingLedger,
    DeltaTimingStage,
)


ACCEPTED_METRIC_LEDGER_REF = "sensiblaw.accepted-metric-ledger.v0_2"
TARGET_POST_PARSER_TO_SPACY_RATIO = 0.10


class MetricGate(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


def _number(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return int(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _timing_from(container: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("numeric_work_timing", "numeric_execution_timing", "parser_receipt"):
        timing = _mapping(container.get(key))
        if timing:
            return timing
    return {}


def extract_parser_receipt(run: Mapping[str, Any]) -> Mapping[str, Any]:
    """Find numeric parser timing in strict/progress/compilation receipt shapes."""

    timing = _timing_from(run)
    if timing:
        return timing

    for key in ("details", "acceptance", "result", "receipt"):
        timing = _timing_from(_mapping(run.get(key)))
        if timing:
            return timing

    artifacts = _mapping(run.get("artifacts"))
    timing = _timing_from(artifacts)
    if timing:
        return timing

    compilation = _mapping(run.get("compilation"))
    timing = _timing_from(compilation)
    if timing:
        return timing
    timing = _timing_from(_mapping(compilation.get("artifacts")))
    if timing:
        return timing

    progress = _mapping(run.get("progress"))
    timing = _timing_from(progress)
    if timing:
        return timing
    return _timing_from(_mapping(progress.get("details")))


@dataclass(frozen=True, slots=True)
class PostParserPhaseLedger:
    numeric_projection_worker_work_ns: int | None
    sentence_closure_worker_work_ns: int | None
    sentence_closure_coordinator_ns: int | None
    sentence_adjacency_ns: int | None
    hierarchy_work_ns: int | None
    paragraph_adjacency_ns: int | None
    lookup_publication_ns: int | None
    summary_work_ns: int | None
    post_parser_coordinator_ns: int | None
    unclassified_orchestration_wall_ns: int | None

    @classmethod
    def from_receipt(cls, receipt: Mapping[str, Any]) -> "PostParserPhaseLedger":
        return cls(
            numeric_projection_worker_work_ns=_number(
                receipt.get("numeric_projection_worker_work_ns")
            ),
            sentence_closure_worker_work_ns=_number(
                receipt.get("sentence_closure_worker_work_ns")
            ),
            sentence_closure_coordinator_ns=_number(
                receipt.get("sentence_closure_coordinator_ns")
            ),
            sentence_adjacency_ns=_number(receipt.get("sentence_adjacency_ns")),
            hierarchy_work_ns=_number(receipt.get("hierarchy_work_ns")),
            paragraph_adjacency_ns=_number(receipt.get("paragraph_adjacency_ns")),
            lookup_publication_ns=_number(receipt.get("lookup_publication_ns")),
            summary_work_ns=_number(receipt.get("summary_work_ns")),
            post_parser_coordinator_ns=_number(
                receipt.get("post_parser_coordinator_ns")
            ),
            unclassified_orchestration_wall_ns=_number(
                receipt.get("unclassified_orchestration_wall_ns")
            ),
        )

    def to_dict(self) -> dict[str, int | None]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def _delta_execution_timing(
    receipt: Mapping[str, Any], phases: PostParserPhaseLedger
) -> DeltaExecutionTimingLedger:
    """Project direct native stage timers into the reusable delta timing ledger.

    This is attribution of measurements already made by the streaming executor,
    not reconstruction from total wall time. Unknown/unclassified wall remains
    unknown and is deliberately not assigned to a synthetic owner.
    """

    ledger = DeltaExecutionTimingLedger()
    if not ledger.enabled:
        return ledger

    fibre_ref = str(receipt.get("source_ref") or "") or None
    token_count = _number(receipt.get("token_count"))
    sentence_count = _number(receipt.get("sentence_count"))
    sentence_pairs = _number(receipt.get("pnf_sentence_adjacent_pairs"))
    paragraph_pairs = _number(receipt.get("pnf_paragraph_adjacent_pairs"))
    visible_rows = _number(receipt.get("pnf_visible_index_rows"))

    rows = (
        (
            DeltaTimingStage.PROJECTION_ATOMS,
            "numeric_projection_worker",
            phases.numeric_projection_worker_work_ns,
            token_count,
            token_count,
        ),
        (
            DeltaTimingStage.LOCAL_REDUCER,
            "sentence_closure_worker",
            phases.sentence_closure_worker_work_ns,
            sentence_count,
            sentence_count,
        ),
        (
            DeltaTimingStage.LOCAL_REDUCER,
            "sentence_closure_coordinator",
            phases.sentence_closure_coordinator_ns,
            sentence_count,
            sentence_count,
        ),
        (
            DeltaTimingStage.LOCAL_REDUCER,
            "sentence_adjacency",
            phases.sentence_adjacency_ns,
            sentence_pairs,
            sentence_pairs,
        ),
        (
            DeltaTimingStage.LOCAL_REDUCER,
            "hierarchy_materialization",
            phases.hierarchy_work_ns,
            sentence_count,
            None,
        ),
        (
            DeltaTimingStage.LOCAL_REDUCER,
            "paragraph_adjacency",
            phases.paragraph_adjacency_ns,
            paragraph_pairs,
            paragraph_pairs,
        ),
        (
            DeltaTimingStage.AUTHORITY_PUBLICATION,
            "global_lookup_publication",
            phases.lookup_publication_ns,
            visible_rows,
            visible_rows,
        ),
    )
    for stage, owner_ref, elapsed_ns, input_units, output_units in rows:
        if elapsed_ns is None:
            continue
        ledger.record(
            stage=stage,
            owner_ref=owner_ref,
            fibre_ref=fibre_ref,
            elapsed_ns=elapsed_ns,
            input_work_units=input_units,
            output_work_units=output_units,
        )
    return ledger


@dataclass(frozen=True, slots=True)
class AcceptedMetricLedger:
    spacy_parser_wall_occupancy_ns: int | None
    post_parser_wall_occupancy_ns: int | None
    parser_post_overlap_ns: int | None
    spacy_parser_only_wall_ns: int | None
    post_parser_only_wall_ns: int | None
    timing_basis: str
    phases: PostParserPhaseLedger
    delta_execution_timing: DeltaExecutionTimingLedger

    @property
    def parser_relative_ratio(self) -> float | None:
        parser = self.spacy_parser_wall_occupancy_ns
        post = self.post_parser_wall_occupancy_ns
        if parser is None or post is None or parser <= 0:
            return None
        if "monotonic-wall-occupancy" not in self.timing_basis:
            return None
        return post / parser

    @property
    def gate(self) -> MetricGate:
        ratio = self.parser_relative_ratio
        if ratio is None:
            return MetricGate.UNKNOWN
        return (
            MetricGate.PASS
            if ratio <= TARGET_POST_PARSER_TO_SPACY_RATIO
            else MetricGate.FAIL
        )

    @property
    def accepted_performance(self) -> bool:
        return self.gate is MetricGate.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": ACCEPTED_METRIC_LEDGER_REF,
            "target_post_parser_to_spacy_ratio": TARGET_POST_PARSER_TO_SPACY_RATIO,
            "gate": self.gate.value,
            "accepted_performance": self.accepted_performance,
            "spacy_parser_wall_occupancy_ns": self.spacy_parser_wall_occupancy_ns,
            "post_parser_wall_occupancy_ns": self.post_parser_wall_occupancy_ns,
            "parser_post_overlap_ns": self.parser_post_overlap_ns,
            "spacy_parser_only_wall_ns": self.spacy_parser_only_wall_ns,
            "post_parser_only_wall_ns": self.post_parser_only_wall_ns,
            "parser_relative_ratio": self.parser_relative_ratio,
            "timing_basis": self.timing_basis,
            "phases": self.phases.to_dict(),
            "delta_execution_timing": self.delta_execution_timing.to_dict(),
            "timing_semantics": (
                "parser/post values are directly measured monotonic occupancy unions; "
                "overlap is retained explicitly and no side is reconstructed from total wall; "
                "delta owner timing attributes already-direct native stage measurements"
            ),
        }


def build_accepted_metric_ledger(run: Mapping[str, Any]) -> AcceptedMetricLedger:
    receipt = extract_parser_receipt(run)
    phases = PostParserPhaseLedger.from_receipt(receipt)
    return AcceptedMetricLedger(
        spacy_parser_wall_occupancy_ns=_number(
            receipt.get("spacy_parser_wall_occupancy_ns")
        ),
        post_parser_wall_occupancy_ns=_number(
            receipt.get("post_parser_wall_occupancy_ns")
        ),
        parser_post_overlap_ns=_number(receipt.get("parser_post_overlap_ns")),
        spacy_parser_only_wall_ns=_number(receipt.get("spacy_parser_only_wall_ns")),
        post_parser_only_wall_ns=_number(receipt.get("post_parser_only_wall_ns")),
        timing_basis=str(receipt.get("timing_basis") or ""),
        phases=phases,
        delta_execution_timing=_delta_execution_timing(receipt, phases),
    )


__all__ = [
    "ACCEPTED_METRIC_LEDGER_REF",
    "AcceptedMetricLedger",
    "MetricGate",
    "PostParserPhaseLedger",
    "TARGET_POST_PARSER_TO_SPACY_RATIO",
    "build_accepted_metric_ledger",
    "extract_parser_receipt",
]
