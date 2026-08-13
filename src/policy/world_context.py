"""Pure numeric contextual evidence for cached world-candidate fibres.

This module intentionally stops at preference evidence.  A context fit can rank or
attach a cached candidate for one mention; it cannot create canonical world identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Mapping


class ContextPolarity(IntEnum):
    CONTRADICTS = -1
    NEUTRAL = 0
    SUPPORTS = 1


@dataclass(frozen=True, slots=True, order=True)
class ContextAxisSymbol:
    axis_kind: int
    symbol_id: int
    polarity: ContextPolarity = ContextPolarity.SUPPORTS

    def __post_init__(self) -> None:
        if self.axis_kind <= 0:
            raise ValueError("axis_kind must be positive")
        if self.symbol_id < 0:
            raise ValueError("symbol_id must be non-negative")


@dataclass(frozen=True, slots=True, order=True)
class CandidateContextRequirement:
    axis_kind: int
    symbol_id: int
    polarity: ContextPolarity = ContextPolarity.SUPPORTS

    def __post_init__(self) -> None:
        if self.polarity is ContextPolarity.NEUTRAL:
            raise ValueError("candidate requirements must be positive or negative")
        if self.axis_kind <= 0:
            raise ValueError("axis_kind must be positive")
        if self.symbol_id < 0:
            raise ValueError("symbol_id must be non-negative")


@dataclass(frozen=True, slots=True)
class ContextFit:
    requirement_count: int
    supporting_count: int
    contradicting_count: int
    unknown_count: int

    @property
    def signed_margin(self) -> int:
        return self.supporting_count - self.contradicting_count

    @property
    def requirements_satisfied(self) -> bool:
        return (
            self.requirement_count > 0
            and self.supporting_count == self.requirement_count
            and self.contradicting_count == 0
            and self.unknown_count == 0
        )


def evaluate_context_fit(
    requirements: Iterable[CandidateContextRequirement],
    observed: Iterable[ContextAxisSymbol],
) -> ContextFit:
    """Compare candidate requirements with mention-local numeric observations.

    Missing observations remain unknown.  They are never converted into negative
    evidence.  Contradiction requires an explicit observation of the opposite
    polarity on the same typed axis/symbol coordinate.
    """
    requirement_tuple = tuple(requirements)
    observed_map: Mapping[tuple[int, int], set[ContextPolarity]] = _observation_map(observed)
    supporting = contradicting = unknown = 0
    for requirement in requirement_tuple:
        polarities = observed_map.get((requirement.axis_kind, requirement.symbol_id), set())
        if requirement.polarity in polarities:
            supporting += 1
        elif ContextPolarity(-int(requirement.polarity)) in polarities:
            contradicting += 1
        else:
            unknown += 1
    return ContextFit(
        requirement_count=len(requirement_tuple),
        supporting_count=supporting,
        contradicting_count=contradicting,
        unknown_count=unknown,
    )


def _observation_map(
    observed: Iterable[ContextAxisSymbol],
) -> dict[tuple[int, int], set[ContextPolarity]]:
    result: dict[tuple[int, int], set[ContextPolarity]] = {}
    for observation in observed:
        if observation.polarity is ContextPolarity.NEUTRAL:
            continue
        result.setdefault((observation.axis_kind, observation.symbol_id), set()).add(
            observation.polarity
        )
    return result
