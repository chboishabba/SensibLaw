"""Constitutional runtime types for consumer-indexed numeric PNF execution.

The Agda layer is the specification; this module is the small Python surface
that prevents runtime code from collapsing distinct semantic/execution axes.
It intentionally contains no database or model-specific scoring policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Callable, Generic, Iterable, Sequence, TypeVar


class EvidenceHorizon(IntEnum):
    """Cumulative relational horizon over one persistent candidate fibre."""

    H3_LOCAL_STRUCTURAL = 3
    H6_DISCOURSE_TEMPORAL = 6
    H9_EXTERNAL_AUTHORITY = 9


class EvidenceFamily(IntEnum):
    LOCAL_STRUCTURAL = 1
    DISCOURSE_TEMPORAL = 2
    EXTERNAL_AUTHORITY = 3

    @property
    def horizon(self) -> EvidenceHorizon:
        return {
            EvidenceFamily.LOCAL_STRUCTURAL: EvidenceHorizon.H3_LOCAL_STRUCTURAL,
            EvidenceFamily.DISCOURSE_TEMPORAL: EvidenceHorizon.H6_DISCOURSE_TEMPORAL,
            EvidenceFamily.EXTERNAL_AUTHORITY: EvidenceHorizon.H9_EXTERNAL_AUTHORITY,
        }[self]


class ExecutionDisposition(str, Enum):
    """Execution state only.  None of these values is semantic refutation."""

    ACTIVE = "active"
    PRUNED_REOPENABLE = "pruned_reopenable"
    RESOURCE_LIMITED = "resource_limited"
    PLANNER_SUPERSEDED = "planner_superseded"


@dataclass(frozen=True, slots=True)
class CandidateKey:
    demand_id: int
    target_kind: int
    target_id: int


@dataclass(frozen=True, slots=True)
class SignedEvidence:
    candidate: CandidateKey
    evidence_ref: str
    family: EvidenceFamily
    signed_residual: int
    provenance_ref: str | None = None

    @property
    def horizon(self) -> EvidenceHorizon:
        return self.family.horizon

    @property
    def phase(self) -> int:
        """Coarse trit derived from the fine signed residual."""
        return phase_of_residual(self.signed_residual)


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    """Independent runtime axes; deliberately not one overloaded status enum."""

    candidate: CandidateKey
    represented_possible: bool
    active: bool
    supported: bool
    preferred: bool
    admissible: bool
    refuted: bool
    execution_disposition: ExecutionDisposition
    refutation_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if self.refuted and not self.refutation_evidence_ref:
            raise ValueError("semantic refutation requires an evidence reference")
        if self.refuted and self.admissible:
            raise ValueError("a currently refuted candidate cannot be admissible")
        if self.active and self.execution_disposition is not ExecutionDisposition.ACTIVE:
            raise ValueError("active candidates must have ACTIVE execution disposition")
        if self.refuted and self.active:
            raise ValueError("a refuted candidate cannot remain on the active execution surface")
        if self.active and not self.represented_possible:
            raise ValueError("active execution must be a subset of the represented candidate fibre")


@dataclass(frozen=True, slots=True)
class RelevanceAccounting:
    """Exact model-relative accounting; values are not presumed probabilities."""

    active_mass: int
    residual_candidate_mass: int
    represented_residual_mass: int
    outside_model_mass: int
    total_mass: int

    def __post_init__(self) -> None:
        values = (
            self.active_mass,
            self.residual_candidate_mass,
            self.represented_residual_mass,
            self.outside_model_mass,
        )
        if self.total_mass <= 0 or any(value < 0 for value in values):
            raise ValueError("relevance masses must be non-negative and total_mass positive")
        if sum(values) != self.total_mass:
            raise ValueError("P + Q + R + O relevance mass must equal total mass")

    @property
    def retained_relevance(self) -> Decimal:
        return Decimal(self.active_mass) / Decimal(self.total_mass)

    @property
    def explicit_ignorance(self) -> Decimal:
        return Decimal(self.outside_model_mass) / Decimal(self.total_mass)


@dataclass(frozen=True, slots=True)
class CompressionObservation:
    represented_candidate_count: int
    active_candidate_count: int
    relevance: RelevanceAccounting

    def __post_init__(self) -> None:
        if self.represented_candidate_count < 0 or self.active_candidate_count < 0:
            raise ValueError("candidate counts cannot be negative")
        if self.active_candidate_count > self.represented_candidate_count:
            raise ValueError("active P must be a subset of represented F")

    @property
    def active_compression_ratio(self) -> Decimal | None:
        if self.represented_candidate_count == 0:
            return None
        return Decimal(self.active_candidate_count) / Decimal(
            self.represented_candidate_count
        )

    @property
    def relevance_per_active_candidate(self) -> Decimal | None:
        """Cantor-style eta_C: represented task relevance per unit active work."""
        if self.active_candidate_count == 0:
            return None
        return self.relevance.retained_relevance / Decimal(self.active_candidate_count)


@dataclass(frozen=True, slots=True)
class StageCost:
    workload_ref: str
    stage_name: str
    input_units: int
    generated_units: int
    retained_units: int
    output_units: int
    work_units: int
    elapsed_microseconds: int
    peak_memory_bytes: int | None = None

    def __post_init__(self) -> None:
        numeric = (
            self.input_units,
            self.generated_units,
            self.retained_units,
            self.output_units,
            self.work_units,
            self.elapsed_microseconds,
        )
        if any(value < 0 for value in numeric):
            raise ValueError("stage cost units cannot be negative")
        if self.peak_memory_bytes is not None and self.peak_memory_bytes < 0:
            raise ValueError("peak memory cannot be negative")


@dataclass(frozen=True, slots=True)
class ScalePoint:
    workload_ref: str
    represented_carrier_units: int
    post_parser_work_units: int

    def __post_init__(self) -> None:
        if self.represented_carrier_units < 0 or self.post_parser_work_units < 0:
            raise ValueError("scale units cannot be negative")


def phase_of_residual(value: int) -> int:
    """Return -1/0/+1 as a projection of a fine signed value."""
    return -1 if value < 0 else (1 if value > 0 else 0)


def progressive_signed_residual(
    evidence: Iterable[SignedEvidence],
    horizon: EvidenceHorizon,
) -> int:
    """Accumulate evidence without rebuilding the candidate fibre at each horizon."""
    return sum(item.signed_residual for item in evidence if item.horizon <= horizon)


def assert_same_candidate_fibre(
    fibres: Sequence[Iterable[CandidateKey]],
) -> None:
    """H3/H6/H9 may expand evidence, never silently recreate candidate identity."""
    canonical: frozenset[CandidateKey] | None = None
    for fibre in fibres:
        current = frozenset(fibre)
        if canonical is None:
            canonical = current
        elif current != canonical:
            raise ValueError("relational horizon changed the represented candidate fibre")


def parser_dominance_ratio(
    *,
    parser_before: StageCost,
    parser_after: StageCost,
    post_parser_after: StageCost,
    minimum_factor: Decimal = Decimal(1),
) -> Decimal | None:
    """Earn parser dominance by cheaper semantics, never by slowing spaCy.

    All three measurements must describe the same workload.  ``None`` is
    returned when post-parser elapsed time is exactly zero (an infinite observed
    ratio); callers may record that separately.
    """

    workload = parser_before.workload_ref
    if parser_after.workload_ref != workload or post_parser_after.workload_ref != workload:
        raise ValueError("parser/post-parser comparisons require the same workload")
    if parser_after.elapsed_microseconds > parser_before.elapsed_microseconds:
        raise ValueError("parser dominance cannot be earned by making the parser slower")
    if parser_after.work_units > parser_before.work_units:
        raise ValueError("parser dominance cannot be earned by increasing parser work")
    if post_parser_after.elapsed_microseconds == 0:
        return None
    ratio = Decimal(parser_after.elapsed_microseconds) / Decimal(
        post_parser_after.elapsed_microseconds
    )
    if ratio < minimum_factor:
        raise ValueError(
            f"parser dominance factor {ratio} is below required {minimum_factor}"
        )
    return ratio


def validate_affine_scale_series(
    points: Sequence[ScalePoint],
    *,
    slope: int,
    intercept: int,
    minimum_points: int = 2,
) -> None:
    """Validate empirical observed scaling; this is not an asymptotic theorem."""

    if slope < 0 or intercept < 0:
        raise ValueError("affine envelope coefficients cannot be negative")
    if len(points) < minimum_points:
        raise ValueError("one benchmark point is not a scaling series")
    for point in points:
        allowed = slope * point.represented_carrier_units + intercept
        if point.post_parser_work_units > allowed:
            raise ValueError(
                f"workload {point.workload_ref!r} exceeded declared work envelope: "
                f"{point.post_parser_work_units} > {allowed}"
            )


StateT = TypeVar("StateT")
ActionT = TypeVar("ActionT")
ObservationT = TypeVar("ObservationT")


@dataclass(frozen=True, slots=True)
class TerminalisationWitness(Generic[StateT, ActionT, ObservationT]):
    left: StateT
    right: StateT
    actions: tuple[ActionT, ...]
    left_after: StateT
    right_after: StateT
    current_observation: ObservationT
    left_future_observation: ObservationT
    right_future_observation: ObservationT


def find_terminalisation_witness(
    *,
    left: StateT,
    right: StateT,
    actions: Sequence[ActionT],
    project: Callable[[StateT], ObservationT],
    step: Callable[[StateT, ActionT], StateT],
) -> TerminalisationWitness[StateT, ActionT, ObservationT] | None:
    """Construct the runtime counterexample used by destructive-projection tests.

    A projection is unsafe for this trace when it identifies the current states
    but the same admissible action sequence makes their future projections
    diverge.  Returning ``None`` proves nothing globally; it only says this
    concrete trace did not expose a defect.
    """

    current_left = project(left)
    current_right = project(right)
    if current_left != current_right:
        return None

    left_after = left
    right_after = right
    for action in actions:
        left_after = step(left_after, action)
        right_after = step(right_after, action)

    left_future = project(left_after)
    right_future = project(right_after)
    if left_future == right_future:
        return None
    return TerminalisationWitness(
        left=left,
        right=right,
        actions=tuple(actions),
        left_after=left_after,
        right_after=right_after,
        current_observation=current_left,
        left_future_observation=left_future,
        right_future_observation=right_future,
    )
