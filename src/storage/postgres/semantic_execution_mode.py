"""Fail-closed routing for semantic sentence execution.

The router is deliberately independent of PostgreSQL and spaCy.  Callers supply
observation thunks so parity can evaluate both implementations before either
publication path is selected.  Publication remains a separate boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


class SemanticExecutionMode(StrEnum):
    """Runtime authority mode for sentence semantic execution."""

    DIRECT = "direct"
    REFERENCE = "reference"
    PARITY = "parity"


class SemanticParityError(RuntimeError):
    """Direct and reference semantic observations disagree."""


@dataclass(frozen=True, slots=True)
class RoutedObservation(Generic[T]):
    """One selected observation plus optional parity evidence."""

    mode: SemanticExecutionMode
    selected: T
    direct: T | None = None
    reference: T | None = None


def parse_semantic_execution_mode(
    value: SemanticExecutionMode | str,
) -> SemanticExecutionMode:
    if isinstance(value, SemanticExecutionMode):
        return value
    try:
        return SemanticExecutionMode(str(value).strip().lower())
    except ValueError as error:
        raise ValueError(
            "semantic execution mode must be one of: direct, reference, parity"
        ) from error


def route_semantic_observation(
    mode: SemanticExecutionMode | str,
    *,
    direct: Callable[[], T],
    reference: Callable[[], T],
) -> RoutedObservation[T]:
    """Select one observation, with parity comparing before publication.

    ``direct`` and ``reference`` must be observation-only thunks.  In parity
    mode both run before this function returns; disagreement raises and gives
    the caller no selected value to publish.
    """

    resolved = parse_semantic_execution_mode(mode)
    if resolved is SemanticExecutionMode.DIRECT:
        observed = direct()
        return RoutedObservation(mode=resolved, selected=observed, direct=observed)
    if resolved is SemanticExecutionMode.REFERENCE:
        observed = reference()
        return RoutedObservation(
            mode=resolved,
            selected=observed,
            reference=observed,
        )

    direct_observation = direct()
    reference_observation = reference()
    if direct_observation != reference_observation:
        raise SemanticParityError(
            "direct/reference semantic parity mismatch; publication aborted"
        )
    return RoutedObservation(
        mode=resolved,
        selected=direct_observation,
        direct=direct_observation,
        reference=reference_observation,
    )


__all__ = [
    "RoutedObservation",
    "SemanticExecutionMode",
    "SemanticParityError",
    "parse_semantic_execution_mode",
    "route_semantic_observation",
]
