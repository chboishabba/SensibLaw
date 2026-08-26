"""Fail-closed sprint constitution for the delta-native PNF execution strategy.

The runtime model mirrors DASHI.Cognition.PNF.DreamFlowSprintConstitutionExact:
O organization, R requirement, C code, S state, L lattice, P proposal,
G governance, and F the gap function.

This module does not create another compiler or semantic authority. It evaluates
whether an execution-strategy proposal is ready to progress or be accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

OrganizationT = TypeVar("OrganizationT")
RequirementT = TypeVar("RequirementT")
CodeT = TypeVar("CodeT")
StateT = TypeVar("StateT")
LatticeT = TypeVar("LatticeT")
ProposalT = TypeVar("ProposalT")
GovernanceT = TypeVar("GovernanceT")


@dataclass(frozen=True, slots=True)
class FormalModel(
    Generic[
        OrganizationT,
        RequirementT,
        CodeT,
        StateT,
        LatticeT,
        ProposalT,
        GovernanceT,
    ]
):
    O: OrganizationT
    R: RequirementT
    C: CodeT
    S: StateT
    L: LatticeT
    P: ProposalT
    G: GovernanceT
    F: Callable[[StateT, ProposalT], int]


@dataclass(frozen=True, slots=True)
class SprintSemantics(
    Generic[
        OrganizationT,
        RequirementT,
        CodeT,
        StateT,
        LatticeT,
        ProposalT,
        GovernanceT,
    ]
):
    constraints: Mapping[str, Callable[[FormalModel], bool]]
    invariants: Mapping[str, Callable[[LatticeT, StateT], bool]]
    preconditions: Mapping[str, Callable[[FormalModel], bool]]
    transition: Callable[[CodeT, ProposalT, StateT], StateT]
    postconditions: Mapping[
        str,
        Callable[[FormalModel, StateT], bool],
    ]


@dataclass(frozen=True, slots=True)
class PhysicalEvidence:
    reference_work: int
    candidate_work: int
    reference_boundary_crossings: int
    candidate_boundary_crossings: int
    reference_wall_ns: int | None = None
    candidate_wall_ns: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "reference_work",
            "candidate_work",
            "reference_boundary_crossings",
            "candidate_boundary_crossings",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be non-negative")
        for name in ("reference_wall_ns", "candidate_wall_ns"):
            value = getattr(self, name)
            if value is not None and int(value) < 0:
                raise ValueError(f"{name} must be non-negative when supplied")

    @property
    def work_no_worse(self) -> bool:
        return self.candidate_work <= self.reference_work

    @property
    def boundary_no_worse(self) -> bool:
        return self.candidate_boundary_crossings <= self.reference_boundary_crossings

    @property
    def wall_measured(self) -> bool:
        return self.reference_wall_ns is not None and self.candidate_wall_ns is not None

    @property
    def wall_no_worse(self) -> bool | None:
        if not self.wall_measured:
            return None
        return int(self.candidate_wall_ns) <= int(self.reference_wall_ns)


@dataclass(frozen=True, slots=True)
class SprintAcceptanceReceipt(Generic[StateT]):
    next_state: StateT
    constraints: Mapping[str, bool]
    invariants_before: Mapping[str, bool]
    preconditions: Mapping[str, bool]
    invariants_after: Mapping[str, bool]
    postconditions: Mapping[str, bool]
    gap_before: int
    gap_after: int
    physical: PhysicalEvidence | None

    @property
    def semantic_ready(self) -> bool:
        return (
            bool(self.constraints)
            and all(self.constraints.values())
            and bool(self.invariants_before)
            and all(self.invariants_before.values())
            and bool(self.preconditions)
            and all(self.preconditions.values())
            and bool(self.invariants_after)
            and all(self.invariants_after.values())
            and bool(self.postconditions)
            and all(self.postconditions.values())
            and self.gap_after <= self.gap_before
        )

    @property
    def gap_closed(self) -> bool:
        return self.gap_after == 0

    @property
    def physical_ready(self) -> bool:
        return bool(
            self.physical
            and self.physical.work_no_worse
            and self.physical.boundary_no_worse
            and self.physical.wall_no_worse is not False
        )

    @property
    def progress_ready(self) -> bool:
        return self.semantic_ready and self.physical_ready

    @property
    def accepted(self) -> bool:
        return self.progress_ready and self.gap_closed

    def as_dict(self) -> dict[str, object]:
        physical = self.physical
        return {
            "contract": "sensiblaw.dream-flow-sprint-constitution.v0_1",
            "constraints": dict(self.constraints),
            "invariants_before": dict(self.invariants_before),
            "preconditions": dict(self.preconditions),
            "invariants_after": dict(self.invariants_after),
            "postconditions": dict(self.postconditions),
            "gap_before": self.gap_before,
            "gap_after": self.gap_after,
            "gap_closed": self.gap_closed,
            "semantic_ready": self.semantic_ready,
            "physical_ready": self.physical_ready,
            "progress_ready": self.progress_ready,
            "accepted": self.accepted,
            "physical": None
            if physical is None
            else {
                "reference_work": physical.reference_work,
                "candidate_work": physical.candidate_work,
                "reference_boundary_crossings": physical.reference_boundary_crossings,
                "candidate_boundary_crossings": physical.candidate_boundary_crossings,
                "reference_wall_ns": physical.reference_wall_ns,
                "candidate_wall_ns": physical.candidate_wall_ns,
                "work_no_worse": physical.work_no_worse,
                "boundary_no_worse": physical.boundary_no_worse,
                "wall_no_worse": physical.wall_no_worse,
            },
        }


def evaluate_sprint_transition(
    model: FormalModel,
    semantics: SprintSemantics,
    *,
    physical: PhysicalEvidence | None = None,
) -> SprintAcceptanceReceipt:
    gap_before = int(model.F(model.S, model.P))
    if gap_before < 0:
        raise ValueError("gap function must be non-negative")

    constraints = {
        name: bool(check(model)) for name, check in semantics.constraints.items()
    }
    invariants_before = {
        name: bool(check(model.L, model.S))
        for name, check in semantics.invariants.items()
    }
    preconditions = {
        name: bool(check(model)) for name, check in semantics.preconditions.items()
    }

    if not constraints or not all(constraints.values()):
        next_state = model.S
    elif not invariants_before or not all(invariants_before.values()):
        next_state = model.S
    elif not preconditions or not all(preconditions.values()):
        next_state = model.S
    else:
        next_state = semantics.transition(model.C, model.P, model.S)

    invariants_after = {
        name: bool(check(model.L, next_state))
        for name, check in semantics.invariants.items()
    }
    postconditions = {
        name: bool(check(model, next_state))
        for name, check in semantics.postconditions.items()
    }
    gap_after = int(model.F(next_state, model.P))
    if gap_after < 0:
        raise ValueError("gap function must be non-negative")

    return SprintAcceptanceReceipt(
        next_state=next_state,
        constraints=constraints,
        invariants_before=invariants_before,
        preconditions=preconditions,
        invariants_after=invariants_after,
        postconditions=postconditions,
        gap_before=gap_before,
        gap_after=gap_after,
        physical=physical,
    )


__all__ = [
    "FormalModel",
    "PhysicalEvidence",
    "SprintAcceptanceReceipt",
    "SprintSemantics",
    "evaluate_sprint_transition",
]
