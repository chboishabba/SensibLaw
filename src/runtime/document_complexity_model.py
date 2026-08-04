"""Executable complexity contracts for document compilation stages.

The contracts distinguish unavoidable input/output-linear work from accidental
repeated-prefix reconstruction.  They are descriptive and auditable: runtime
receipts record actual units, boundary/interface work, revisions, demands, and
flattened descendant bytes without claiming an asymptotic class from one sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import ceil, log
from typing import Iterable


class ComplexityTarget(StrEnum):
    INPUT_LINEAR = "input_linear"
    OUTPUT_LINEAR = "output_linear"
    SPARSE_GRAPH_LINEAR = "sparse_graph_linear"
    DIFFERENTIAL = "differential"
    INTERFACE_SENSITIVE = "interface_sensitive"


@dataclass(frozen=True)
class StageComplexityContract:
    stage: str
    target: ComplexityTarget
    lower_bound: str
    target_bound: str
    accidental_antipattern: str
    work_variables: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "target": self.target.value,
            "lower_bound": self.lower_bound,
            "target_bound": self.target_bound,
            "accidental_antipattern": self.accidental_antipattern,
            "work_variables": list(self.work_variables),
        }


DOCUMENT_STAGE_COMPLEXITY: dict[str, StageComplexityContract] = {
    "parser_annotation": StageComplexityContract(
        stage="parser_annotation",
        target=ComplexityTarget.INPUT_LINEAR,
        lower_bound="Omega(chars + tokens)",
        target_bound="Theta(chars + tokens + leaves * overlap)",
        accidental_antipattern="reparse every completed prefix",
        work_variables=("chars", "tokens", "leaves", "overlap"),
    ),
    "parser_observation_projection": StageComplexityContract(
        stage="parser_observation_projection",
        target=ComplexityTarget.SPARSE_GRAPH_LINEAR,
        lower_bound="Omega(tokens + atoms)",
        target_bound="Theta(tokens + atoms + local_relations + cross_relations)",
        accidental_antipattern="lookup or reconstruct against every prior atom",
        work_variables=(
            "tokens",
            "atoms",
            "local_relations",
            "cross_relations",
            "lookup_operations",
        ),
    ),
    "base_proposal_generation": StageComplexityContract(
        stage="base_proposal_generation",
        target=ComplexityTarget.OUTPUT_LINEAR,
        lower_bound="Omega(atoms + proposals)",
        target_bound="Theta(atoms + relations + proposals)",
        accidental_antipattern="rebuild proposal indexes per proposal",
        work_variables=("atoms", "relations", "proposals"),
    ),
    "streaming_closure": StageComplexityContract(
        stage="streaming_closure",
        target=ComplexityTarget.DIFFERENTIAL,
        lower_bound="Omega(jobs + changed_factors)",
        target_bound="Theta(jobs + proposals + affected_owner_groups)",
        accidental_antipattern="scan all proposals for every dirty owner",
        work_variables=("jobs", "proposals", "affected_owner_groups"),
    ),
    "hierarchical_graph_reduction": StageComplexityContract(
        stage="hierarchical_graph_reduction",
        target=ComplexityTarget.INTERFACE_SENSITIVE,
        lower_bound="Omega(leaves + cross_relations)",
        target_bound="Theta(leaves + sum_interfaces + cross_relations + demands)",
        accidental_antipattern="flatten descendant interiors at every parent",
        work_variables=(
            "leaves",
            "sum_interfaces",
            "cross_relations",
            "demands",
            "descendant_bytes_reconstructed",
        ),
    ),
    "constraint_assessment": StageComplexityContract(
        stage="constraint_assessment",
        target=ComplexityTarget.DIFFERENTIAL,
        lower_bound="Omega(constraints)",
        target_bound="Theta(constraints + affected_constraint_edges)",
        accidental_antipattern="rescan every constraint after every revision",
        work_variables=("constraints", "affected_constraint_edges", "revisions"),
    ),
    "meet_refinement": StageComplexityContract(
        stage="meet_refinement",
        target=ComplexityTarget.DIFFERENTIAL,
        lower_bound="Omega(revisions)",
        target_bound="Theta(revisions + alternatives_examined)",
        accidental_antipattern="retain and serialise full prior/result graph generations",
        work_variables=("revisions", "alternatives_examined"),
    ),
    "demand_derivation": StageComplexityContract(
        stage="demand_derivation",
        target=ComplexityTarget.DIFFERENTIAL,
        lower_bound="Omega(factors + constraints)",
        target_bound="Theta(factors + constraints + affected_demands)",
        accidental_antipattern="derive all demands again after each local change",
        work_variables=("factors", "constraints", "affected_demands"),
    ),
    "postgres_persistence": StageComplexityContract(
        stage="postgres_persistence",
        target=ComplexityTarget.OUTPUT_LINEAR,
        lower_bound="Omega(rows)",
        target_bound="Theta(rows + bytes)",
        accidental_antipattern="serialise every complete graph generation",
        work_variables=("rows", "bytes", "graph_generations"),
    ),
}


@dataclass(frozen=True)
class BatchComplexitySample:
    completed_units: int
    elapsed_ms: int
    process_tree_rss_bytes: int = 0
    gc_collections: int = 0
    lookup_operations: int = 0
    retained_objects: int = 0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

    def to_dict(self) -> dict[str, int]:
        return {
            "completed_units": self.completed_units,
            "elapsed_ms": self.elapsed_ms,
            "process_tree_rss_bytes": self.process_tree_rss_bytes,
            "gc_collections": self.gc_collections,
            "lookup_operations": self.lookup_operations,
            "retained_objects": self.retained_objects,
        }


@dataclass(frozen=True)
class BatchInterval:
    start_units: int
    end_units: int
    units: int
    elapsed_ms: int
    units_per_second: float
    milliseconds_per_unit: float
    rss_delta_bytes: int
    gc_collections_delta: int
    lookup_operations_delta: int
    retained_objects_delta: int

    def to_dict(self) -> dict[str, object]:
        return {
            "start_units": self.start_units,
            "end_units": self.end_units,
            "units": self.units,
            "elapsed_ms": self.elapsed_ms,
            "units_per_second": self.units_per_second,
            "milliseconds_per_unit": self.milliseconds_per_unit,
            "rss_delta_bytes": self.rss_delta_bytes,
            "gc_collections_delta": self.gc_collections_delta,
            "lookup_operations_delta": self.lookup_operations_delta,
            "retained_objects_delta": self.retained_objects_delta,
        }


@dataclass(frozen=True)
class BatchTrendReceipt:
    intervals: tuple[BatchInterval, ...]
    first_rate: float | None
    latest_rate: float | None
    rate_ratio: float | None
    slowdown_fraction: float | None
    monotone_cost_increase: bool
    comparable_intervals: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "intervals": [row.to_dict() for row in self.intervals],
            "first_rate": self.first_rate,
            "latest_rate": self.latest_rate,
            "rate_ratio": self.rate_ratio,
            "slowdown_fraction": self.slowdown_fraction,
            "monotone_cost_increase": self.monotone_cost_increase,
            "comparable_intervals": self.comparable_intervals,
        }


def batch_trend_receipt(
    samples: Iterable[BatchComplexitySample],
) -> BatchTrendReceipt:
    """Calculate consecutive interval rates; never infer from cumulative averages."""

    ordered = tuple(samples)
    intervals: list[BatchInterval] = []
    for prior, current in zip(ordered, ordered[1:]):
        units = current.completed_units - prior.completed_units
        elapsed_ms = current.elapsed_ms - prior.elapsed_ms
        if units <= 0 or elapsed_ms <= 0:
            continue
        intervals.append(
            BatchInterval(
                start_units=prior.completed_units,
                end_units=current.completed_units,
                units=units,
                elapsed_ms=elapsed_ms,
                units_per_second=units * 1000.0 / elapsed_ms,
                milliseconds_per_unit=elapsed_ms / units,
                rss_delta_bytes=(
                    current.process_tree_rss_bytes - prior.process_tree_rss_bytes
                ),
                gc_collections_delta=current.gc_collections - prior.gc_collections,
                lookup_operations_delta=(
                    current.lookup_operations - prior.lookup_operations
                ),
                retained_objects_delta=current.retained_objects
                - prior.retained_objects,
            )
        )

    comparable = bool(intervals) and len({row.units for row in intervals}) == 1
    first_rate = intervals[0].units_per_second if intervals else None
    latest_rate = intervals[-1].units_per_second if intervals else None
    ratio = (
        latest_rate / first_rate
        if first_rate is not None and latest_rate is not None and first_rate > 0
        else None
    )
    slowdown = 1.0 - ratio if ratio is not None else None
    costs = [row.milliseconds_per_unit for row in intervals]
    monotone = len(costs) > 1 and all(
        current >= prior for prior, current in zip(costs, costs[1:])
    )
    return BatchTrendReceipt(
        intervals=tuple(intervals),
        first_rate=first_rate,
        latest_rate=latest_rate,
        rate_ratio=ratio,
        slowdown_fraction=slowdown,
        monotone_cost_increase=monotone,
        comparable_intervals=comparable,
    )


def repeated_prefix_work(primitive_units: int, leaf_capacity: int) -> int:
    """Return b(1 + ... + L), the work of rebuilding every completed prefix."""

    if primitive_units < 0 or leaf_capacity < 1:
        raise ValueError(
            "primitive_units must be non-negative and leaf_capacity positive"
        )
    leaves = ceil(primitive_units / leaf_capacity)
    return leaf_capacity * leaves * (leaves + 1) // 2


def hierarchy_node_count(leaf_count: int, arity: int) -> int:
    """Exact node count including partial final groups at each level."""

    if leaf_count < 1 or arity < 2:
        raise ValueError("leaf_count must be positive and arity at least two")
    total = leaf_count
    current = leaf_count
    while current > 1:
        current = ceil(current / arity)
        total += current
    return total


def hierarchy_depth(leaf_count: int, arity: int) -> int:
    if leaf_count < 1 or arity < 2:
        raise ValueError("leaf_count must be positive and arity at least two")
    return 0 if leaf_count == 1 else ceil(log(leaf_count, arity))


def stage_complexity_contract(stage: str) -> StageComplexityContract:
    try:
        return DOCUMENT_STAGE_COMPLEXITY[stage]
    except KeyError as error:
        raise ValueError(f"undeclared complexity stage: {stage}") from error


__all__ = [
    "BatchComplexitySample",
    "BatchInterval",
    "BatchTrendReceipt",
    "ComplexityTarget",
    "DOCUMENT_STAGE_COMPLEXITY",
    "StageComplexityContract",
    "batch_trend_receipt",
    "hierarchy_depth",
    "hierarchy_node_count",
    "repeated_prefix_work",
    "stage_complexity_contract",
]
