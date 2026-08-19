"""Fail-closed parser-relative acceptance timing for strict numeric PNF.

The numeric streaming runtime already emits direct monotonic occupancy and named
post-parser kernel measurements.  This module normalizes that evidence without
inventing stage time by subtraction and makes missing attribution explicit.

A completed semantic run is not a performance acceptance result unless this
ledger can establish both sides of the parser-relative target.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


ACCEPTED_METRIC_LEDGER_REF = "sensiblaw.accepted-metric-ledger.v0_1"
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


def extract_parser_receipt(run: Mapping[str, Any]) -> Mapping[str, Any]:
    """Find the numeric parser timing carrier in accepted runtime shapes."""

    direct = _mapping(run.get("parser_receipt"))
    if direct:
        return direct
    artifacts = _mapping(run.get("artifacts"))
    nested = _mapping(artifacts.get("parser_receipt"))
    if nested:
        return nested
    compilation = _mapping(run.get("compilation"))
    artifacts = _mapping(compilation.get("artifacts"))
    nested = _mapping(artifacts.get("parser_receipt"))
    if nested:
        return nested
    timing = _mapping(run.get("numeric_work_timing"))
    return timing


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
            post_parser_coordinator_ns=_number(receipt.get("post_parser_coordinator_ns")),
            unclassified_orchestration_wall_ns=_number(
                receipt.get("unclassified_orchestration_wall_ns")
            ),
        )

    def to_dict(self) -> dict[str, int | None]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class AcceptedMetricLedger:
    spacy_parser_wall_occupancy_ns: int | None
    post_parser_wall_occupancy_ns: int | None
    parser_post_overlap_ns: int | None
    spacy_parser_only_wall_ns: int | None
    post_parser_only_wall_ns: int | None
    timing_basis: str
    phases: PostParserPhaseLedger

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
            "timing_semantics": (
                "parser/post values are directly measured monotonic occupancy unions; "
                "overlap is retained explicitly and no side is reconstructed from total wall"
            ),
        }


def build_accepted_metric_ledger(run: Mapping[str, Any]) -> AcceptedMetricLedger:
    receipt = extract_parser_receipt(run)
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
        phases=PostParserPhaseLedger.from_receipt(receipt),
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
