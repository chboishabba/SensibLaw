"""Optimization-economy receipts for SensibLaw/ITIR.

Runtime performance and implementation/change economy are deliberately separate
axes. These receipts do not grant semantic authority; they summarize measured
or reviewed costs after semantic parity/admissibility has been established.

The central review question is no longer only ``does this implementation work?``
but also ``is this computation expressed in the cheapest equivalent
representation?``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence


OPTIMIZATION_ECONOMY_REF = "sensiblaw.optimization-economy.v0_2"


class ParetoState(StrEnum):
    IMPROVEMENT = "improvement"
    EQUIVALENT = "equivalent"
    TRADEOFF = "tradeoff"
    REGRESSION = "regression"
    UNKNOWN = "unknown"


def _ratio(numerator: int, denominator: int) -> float | None:
    if numerator < 0 or denominator < 0:
        raise ValueError("optimization counts must be non-negative")
    if denominator == 0:
        return 0.0 if numerator == 0 else None
    return numerator / denominator


@dataclass(frozen=True, slots=True)
class AmplificationReceipt:
    """Legacy broad physical-amplification surface.

    This remains for compatibility with existing receipts. New relational
    hotspots should additionally use :class:`RelationalWorkReceipt`, which
    distinguishes rows scanned from rows admitted and rows entering a quotient
    or grouping stage.
    """

    touched_semantic_rows: int
    historical_rows_examined: int
    attempted_writes: int
    semantically_new_writes: int

    @property
    def history_read_amplification(self) -> float | None:
        return _ratio(self.historical_rows_examined, self.touched_semantic_rows)

    @property
    def write_amplification(self) -> float | None:
        return _ratio(self.attempted_writes, self.semantically_new_writes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "touched_semantic_rows": self.touched_semantic_rows,
            "historical_rows_examined": self.historical_rows_examined,
            "attempted_writes": self.attempted_writes,
            "semantically_new_writes": self.semantically_new_writes,
            "history_read_amplification": self.history_read_amplification,
            "write_amplification": self.write_amplification,
        }


@dataclass(frozen=True, slots=True)
class RelationalWorkReceipt:
    """Cardinality flow through one relational kernel.

    ``rows_scanned`` and ``rows_grouped`` are deliberately distinct. Predicate
    pushdown may reduce hash/sort/group work without reducing underlying table
    reads; a performance claim must not silently identify those two effects.
    """

    rows_scanned: int
    rows_admitted: int
    rows_grouped: int
    rows_output: int
    attempted_writes: int = 0
    committed_writes: int = 0

    def __post_init__(self) -> None:
        values = (
            self.rows_scanned,
            self.rows_admitted,
            self.rows_grouped,
            self.rows_output,
            self.attempted_writes,
            self.committed_writes,
        )
        if any(value < 0 for value in values):
            raise ValueError("relational work counts must be non-negative")

    @property
    def scan_amplification(self) -> float | None:
        return _ratio(self.rows_scanned, self.rows_output)

    @property
    def quotient_amplification(self) -> float | None:
        return _ratio(self.rows_grouped, self.rows_output)

    @property
    def admission_selectivity(self) -> float | None:
        return _ratio(self.rows_admitted, self.rows_scanned)

    @property
    def grouping_input_reduction(self) -> float | None:
        selectivity = self.admission_selectivity
        return None if selectivity is None else 1.0 - selectivity

    @property
    def write_amplification(self) -> float | None:
        return _ratio(self.attempted_writes, self.committed_writes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_scanned": self.rows_scanned,
            "rows_admitted": self.rows_admitted,
            "rows_grouped": self.rows_grouped,
            "rows_output": self.rows_output,
            "attempted_writes": self.attempted_writes,
            "committed_writes": self.committed_writes,
            "scan_amplification": self.scan_amplification,
            "quotient_amplification": self.quotient_amplification,
            "admission_selectivity": self.admission_selectivity,
            "grouping_input_reduction": self.grouping_input_reduction,
            "write_amplification": self.write_amplification,
        }


@dataclass(frozen=True, slots=True)
class ConcentrationPoint:
    k: int
    work: int
    fraction: float


def concentration_profile(
    workloads: Iterable[int], *, ks: Sequence[int] = (1, 10)
) -> tuple[ConcentrationPoint, ...]:
    """Record heavy-tail work concentration instead of smearing it into a mean."""

    ordered = sorted((int(work) for work in workloads), reverse=True)
    if any(work < 0 for work in ordered):
        raise ValueError("workloads must be non-negative")
    total = sum(ordered)
    points: list[ConcentrationPoint] = []
    for requested_k in ks:
        if requested_k < 1:
            raise ValueError("concentration k must be positive")
        k = min(int(requested_k), len(ordered))
        work = sum(ordered[:k])
        fraction = 0.0 if total == 0 else work / total
        points.append(ConcentrationPoint(k=k, work=work, fraction=fraction))
    return tuple(points)


@dataclass(frozen=True, slots=True)
class RuntimeEconomy:
    wall_ns: int
    semantic_work_units: int
    peak_rss_bytes: int
    io_units: int
    amplification: AmplificationReceipt
    reused_work_units: int = 0
    new_work_units: int = 0
    relational_work: RelationalWorkReceipt | None = None

    @property
    def reuse_ratio(self) -> float | None:
        return _ratio(
            self.reused_work_units,
            self.reused_work_units + self.new_work_units,
        )

    def cost_vector(self) -> tuple[int, ...]:
        return (
            self.wall_ns,
            self.semantic_work_units,
            self.peak_rss_bytes,
            self.io_units,
            self.amplification.historical_rows_examined,
            self.amplification.attempted_writes,
            self.new_work_units,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_ns": self.wall_ns,
            "semantic_work_units": self.semantic_work_units,
            "peak_rss_bytes": self.peak_rss_bytes,
            "io_units": self.io_units,
            "reused_work_units": self.reused_work_units,
            "new_work_units": self.new_work_units,
            "reuse_ratio": self.reuse_ratio,
            "amplification": self.amplification.to_dict(),
            "relational_work": (
                None if self.relational_work is None else self.relational_work.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class ArchitectureEconomy:
    """Change-economy counts for one feature/optimization tranche.

    LOC is intentionally absent from the authority vector. ``new_primitives``
    and especially ``new_authority_surfaces`` / ``new_execution_engines`` track
    genuinely new semantic degrees of freedom; ``reused_capabilities`` records
    composition of existing generic machinery; ``retired_compatibility_surfaces``
    is a benefit coordinate.
    """

    new_primitives: int = 0
    new_authority_surfaces: int = 0
    new_execution_engines: int = 0
    new_persistent_schemas: int = 0
    duplicated_capabilities: int = 0
    reused_capabilities: int = 0
    retired_compatibility_surfaces: int = 0

    def novelty_burden(self, weights: Mapping[str, int] | None = None) -> int:
        w = {
            "new_primitives": 1,
            "new_authority_surfaces": 4,
            "new_execution_engines": 4,
            "new_persistent_schemas": 2,
            "duplicated_capabilities": 5,
        }
        if weights is not None:
            unknown = set(weights) - set(w)
            if unknown:
                raise ValueError(f"unknown novelty weights: {sorted(unknown)}")
            w.update({key: int(value) for key, value in weights.items()})
        if any(value < 0 for value in w.values()):
            raise ValueError("novelty weights must be non-negative")
        return (
            self.new_primitives * w["new_primitives"]
            + self.new_authority_surfaces * w["new_authority_surfaces"]
            + self.new_execution_engines * w["new_execution_engines"]
            + self.new_persistent_schemas * w["new_persistent_schemas"]
            + self.duplicated_capabilities * w["duplicated_capabilities"]
        )

    @property
    def capability_reuse_ratio(self) -> float | None:
        return _ratio(
            self.reused_capabilities,
            self.reused_capabilities + self.new_primitives,
        )

    def cost_vector(self) -> tuple[int, ...]:
        return (
            self.new_primitives,
            self.new_authority_surfaces,
            self.new_execution_engines,
            self.new_persistent_schemas,
            self.duplicated_capabilities,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_primitives": self.new_primitives,
            "new_authority_surfaces": self.new_authority_surfaces,
            "new_execution_engines": self.new_execution_engines,
            "new_persistent_schemas": self.new_persistent_schemas,
            "duplicated_capabilities": self.duplicated_capabilities,
            "reused_capabilities": self.reused_capabilities,
            "retired_compatibility_surfaces": self.retired_compatibility_surfaces,
            "novelty_burden": self.novelty_burden(),
            "capability_reuse_ratio": self.capability_reuse_ratio,
        }


@dataclass(frozen=True, slots=True)
class OptimizationEconomyReceipt:
    runtime: RuntimeEconomy
    architecture: ArchitectureEconomy
    semantic_parity_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_ref": OPTIMIZATION_ECONOMY_REF,
            "semantic_parity_ref": self.semantic_parity_ref,
            "runtime": self.runtime.to_dict(),
            "architecture": self.architecture.to_dict(),
        }


def compare_pareto(
    before: OptimizationEconomyReceipt,
    after: OptimizationEconomyReceipt,
) -> ParetoState:
    """Compare only receipts sharing one explicit semantic-parity boundary."""

    if (
        not before.semantic_parity_ref
        or before.semantic_parity_ref != after.semantic_parity_ref
    ):
        return ParetoState.UNKNOWN

    before_costs = before.runtime.cost_vector() + before.architecture.cost_vector()
    after_costs = after.runtime.cost_vector() + after.architecture.cost_vector()
    non_worse = all(
        after_cost <= before_cost
        for after_cost, before_cost in zip(after_costs, before_costs, strict=True)
    )
    any_better = any(
        after_cost < before_cost
        for after_cost, before_cost in zip(after_costs, before_costs, strict=True)
    )
    retirement_non_worse = (
        after.architecture.retired_compatibility_surfaces
        >= before.architecture.retired_compatibility_surfaces
    )
    retirement_better = (
        after.architecture.retired_compatibility_surfaces
        > before.architecture.retired_compatibility_surfaces
    )

    if non_worse and retirement_non_worse:
        if any_better or retirement_better:
            return ParetoState.IMPROVEMENT
        return ParetoState.EQUIVALENT

    all_worse_or_equal = all(
        after_cost >= before_cost
        for after_cost, before_cost in zip(after_costs, before_costs, strict=True)
    ) and (
        after.architecture.retired_compatibility_surfaces
        <= before.architecture.retired_compatibility_surfaces
    )
    any_worse = any(
        after_cost > before_cost
        for after_cost, before_cost in zip(after_costs, before_costs, strict=True)
    ) or (
        after.architecture.retired_compatibility_surfaces
        < before.architecture.retired_compatibility_surfaces
    )
    if all_worse_or_equal and any_worse:
        return ParetoState.REGRESSION
    return ParetoState.TRADEOFF


__all__ = [
    "AmplificationReceipt",
    "ArchitectureEconomy",
    "ConcentrationPoint",
    "OPTIMIZATION_ECONOMY_REF",
    "OptimizationEconomyReceipt",
    "ParetoState",
    "RelationalWorkReceipt",
    "RuntimeEconomy",
    "compare_pareto",
    "concentration_profile",
]
