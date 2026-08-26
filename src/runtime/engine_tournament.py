"""Fail-closed execution-engine tournament for dream-flow kernels.

Technology names carry no authority. A candidate engine is admissible only when
its output is semantically equivalent to the reference for every supplied
workload. Promotion additionally requires no-worse median CPU/boundary work and
a strict median wall-time win on at least one workload.

The semantic equivalence function is caller supplied so relational/set-valued
specifications need not be collapsed to Python object equality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median
from time import monotonic_ns, process_time_ns
from typing import Callable, Generic, Iterable, TypeVar

InputT = TypeVar("InputT")
AuthorityT = TypeVar("AuthorityT")


class KernelGeometry(str, Enum):
    LOCAL_BOUNDED_FIBRE = "local-bounded-fibre"
    GLOBAL_INDEXED_EXPOSURE = "global-indexed-exposure"
    SPARSE_DELTA_CLOSURE = "sparse-delta-closure"


@dataclass(frozen=True, slots=True)
class KernelOutcome(Generic[AuthorityT]):
    authority: AuthorityT
    boundary_crossings: int = 0
    bytes_read: int = 0
    bytes_written: int = 0

    def __post_init__(self) -> None:
        for name in ("boundary_crossings", "bytes_read", "bytes_written"):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class EngineKernel(Generic[InputT, AuthorityT]):
    engine_name: str
    geometry: KernelGeometry
    run: Callable[[InputT], KernelOutcome[AuthorityT]]


@dataclass(frozen=True, slots=True)
class TrialMeasurement(Generic[AuthorityT]):
    authority: AuthorityT
    wall_ns: int
    cpu_ns: int
    boundary_crossings: int
    bytes_read: int
    bytes_written: int


@dataclass(frozen=True, slots=True)
class WorkloadComparison:
    workload_ordinal: int
    authority_equivalent: bool
    reference_wall_ns: int
    candidate_wall_ns: int
    reference_cpu_ns: int
    candidate_cpu_ns: int
    reference_boundary_crossings: int
    candidate_boundary_crossings: int
    reference_bytes_read: int
    candidate_bytes_read: int
    reference_bytes_written: int
    candidate_bytes_written: int

    @property
    def wall_no_worse(self) -> bool:
        return self.candidate_wall_ns <= self.reference_wall_ns

    @property
    def cpu_no_worse(self) -> bool:
        return self.candidate_cpu_ns <= self.reference_cpu_ns

    @property
    def boundary_no_worse(self) -> bool:
        return self.candidate_boundary_crossings <= self.reference_boundary_crossings

    @property
    def strict_wall_win(self) -> bool:
        return self.candidate_wall_ns < self.reference_wall_ns


@dataclass(frozen=True, slots=True)
class EngineTournamentReceipt:
    reference_engine: str
    candidate_engine: str
    geometry: KernelGeometry
    repeats: int
    comparisons: tuple[WorkloadComparison, ...]

    @property
    def authority_exact(self) -> bool:
        return bool(self.comparisons) and all(
            comparison.authority_equivalent for comparison in self.comparisons
        )

    @property
    def earns_keep(self) -> bool:
        return self.authority_exact and all(
            comparison.wall_no_worse
            and comparison.cpu_no_worse
            and comparison.boundary_no_worse
            for comparison in self.comparisons
        )

    @property
    def promotion_ready(self) -> bool:
        return self.earns_keep and any(
            comparison.strict_wall_win for comparison in self.comparisons
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": "sensiblaw.execution-engine-tournament.v0_1",
            "reference_engine": self.reference_engine,
            "candidate_engine": self.candidate_engine,
            "geometry": self.geometry.value,
            "repeats": self.repeats,
            "authority_exact": self.authority_exact,
            "earns_keep": self.earns_keep,
            "promotion_ready": self.promotion_ready,
            "comparisons": [
                {
                    "workload_ordinal": item.workload_ordinal,
                    "authority_equivalent": item.authority_equivalent,
                    "reference_wall_ns": item.reference_wall_ns,
                    "candidate_wall_ns": item.candidate_wall_ns,
                    "reference_cpu_ns": item.reference_cpu_ns,
                    "candidate_cpu_ns": item.candidate_cpu_ns,
                    "reference_boundary_crossings": item.reference_boundary_crossings,
                    "candidate_boundary_crossings": item.candidate_boundary_crossings,
                    "reference_bytes_read": item.reference_bytes_read,
                    "candidate_bytes_read": item.candidate_bytes_read,
                    "reference_bytes_written": item.reference_bytes_written,
                    "candidate_bytes_written": item.candidate_bytes_written,
                    "wall_no_worse": item.wall_no_worse,
                    "cpu_no_worse": item.cpu_no_worse,
                    "boundary_no_worse": item.boundary_no_worse,
                    "strict_wall_win": item.strict_wall_win,
                }
                for item in self.comparisons
            ],
        }


def _measure_once(
    kernel: EngineKernel[InputT, AuthorityT],
    workload: InputT,
) -> TrialMeasurement[AuthorityT]:
    cpu_started = process_time_ns()
    wall_started = monotonic_ns()
    outcome = kernel.run(workload)
    wall_ns = monotonic_ns() - wall_started
    cpu_ns = process_time_ns() - cpu_started
    return TrialMeasurement(
        authority=outcome.authority,
        wall_ns=wall_ns,
        cpu_ns=cpu_ns,
        boundary_crossings=outcome.boundary_crossings,
        bytes_read=outcome.bytes_read,
        bytes_written=outcome.bytes_written,
    )


def _median_int(values: Iterable[int]) -> int:
    return int(median(tuple(values)))


def run_engine_tournament(
    *,
    reference: EngineKernel[InputT, AuthorityT],
    candidate: EngineKernel[InputT, AuthorityT],
    workloads: Iterable[InputT],
    equivalent: Callable[[AuthorityT, AuthorityT], bool] | None = None,
    repeats: int = 3,
) -> EngineTournamentReceipt:
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if reference.geometry != candidate.geometry:
        raise ValueError("engine candidates must be compared on the same kernel geometry")
    equivalent = equivalent or (lambda left, right: left == right)

    comparisons: list[WorkloadComparison] = []
    for ordinal, workload in enumerate(tuple(workloads)):
        reference_trials = tuple(
            _measure_once(reference, workload) for _ in range(repeats)
        )
        candidate_trials = tuple(
            _measure_once(candidate, workload) for _ in range(repeats)
        )
        authority_equivalent = all(
            equivalent(reference_trial.authority, candidate_trial.authority)
            for reference_trial in reference_trials
            for candidate_trial in candidate_trials
        )
        comparisons.append(
            WorkloadComparison(
                workload_ordinal=ordinal,
                authority_equivalent=authority_equivalent,
                reference_wall_ns=_median_int(t.wall_ns for t in reference_trials),
                candidate_wall_ns=_median_int(t.wall_ns for t in candidate_trials),
                reference_cpu_ns=_median_int(t.cpu_ns for t in reference_trials),
                candidate_cpu_ns=_median_int(t.cpu_ns for t in candidate_trials),
                reference_boundary_crossings=_median_int(
                    t.boundary_crossings for t in reference_trials
                ),
                candidate_boundary_crossings=_median_int(
                    t.boundary_crossings for t in candidate_trials
                ),
                reference_bytes_read=_median_int(t.bytes_read for t in reference_trials),
                candidate_bytes_read=_median_int(t.bytes_read for t in candidate_trials),
                reference_bytes_written=_median_int(
                    t.bytes_written for t in reference_trials
                ),
                candidate_bytes_written=_median_int(
                    t.bytes_written for t in candidate_trials
                ),
            )
        )

    return EngineTournamentReceipt(
        reference_engine=reference.engine_name,
        candidate_engine=candidate.engine_name,
        geometry=reference.geometry,
        repeats=repeats,
        comparisons=tuple(comparisons),
    )


__all__ = [
    "EngineKernel",
    "EngineTournamentReceipt",
    "KernelGeometry",
    "KernelOutcome",
    "TrialMeasurement",
    "WorkloadComparison",
    "run_engine_tournament",
]
