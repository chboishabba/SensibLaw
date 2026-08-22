"""Rank optimisation attention by absolute production wall-time exposure.

Percentage speedups are intentionally secondary. A kernel taking seconds must
not displace a minutes/hours phase merely because the small kernel is easier to
improve. This module is measurement policy only; it does not alter semantic
execution or claim that a measured phase can actually be removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MeasuredPhase:
    name: str
    wall_ns: int
    production_required: bool = True

    def __post_init__(self) -> None:
        if self.wall_ns < 0:
            raise ValueError("phase wall_ns must be nonnegative")


@dataclass(frozen=True, slots=True)
class OptimizationAttention:
    name: str
    wall_ns: int
    wall_seconds: float
    horizon: str
    production_required: bool
    first_question: str


def wall_horizon(wall_ns: int) -> str:
    seconds = wall_ns / 1_000_000_000
    if seconds >= 3600:
        return "hours"
    if seconds >= 60:
        return "minutes"
    if seconds >= 1:
        return "seconds"
    return "subsecond"


def rank_optimization_attention(
    phases: Iterable[MeasuredPhase],
) -> tuple[OptimizationAttention, ...]:
    """Return phases in descending absolute wall-time order.

    `production_required=False` deliberately changes the first question from
    "make this faster" to "remove/bypass this from production". It does not
    artificially lower the phase's rank: a two-hour compatibility phase still
    deserves attention until it is actually off the critical path.
    """

    ordered = sorted(phases, key=lambda phase: (-phase.wall_ns, phase.name))
    return tuple(
        OptimizationAttention(
            name=phase.name,
            wall_ns=phase.wall_ns,
            wall_seconds=phase.wall_ns / 1_000_000_000,
            horizon=wall_horizon(phase.wall_ns),
            production_required=phase.production_required,
            first_question=(
                "optimize_required_work"
                if phase.production_required
                else "remove_or_bypass_from_production"
            ),
        )
        for phase in ordered
    )


__all__ = [
    "MeasuredPhase",
    "OptimizationAttention",
    "rank_optimization_attention",
    "wall_horizon",
]
