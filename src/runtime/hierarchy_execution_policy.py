"""Configuration for persistent mini/midi/mega graph execution.

The policy selects the physical hierarchy only. It cannot change semantic
identity, reduction rules, source coordinates, or the canonical document graph.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from src.runtime.hierarchical_graph_execution import HierarchyPlan


@dataclass(frozen=True)
class HierarchyExecutionPolicy:
    leaf_capacity: int = 4096
    arity: int = 4

    def __post_init__(self) -> None:
        if self.leaf_capacity < 1:
            raise ValueError("hierarchy leaf capacity must be positive")
        if self.arity < 2:
            raise ValueError("hierarchy arity must be at least two")

    def build_plan(
        self,
        *,
        document_ref: str,
        primitive_unit_count: int,
        unit: str,
    ) -> HierarchyPlan:
        return HierarchyPlan.build(
            document_ref=document_ref,
            primitive_unit_count=primitive_unit_count,
            leaf_capacity=self.leaf_capacity,
            arity=self.arity,
            unit=unit,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "leaf_capacity": self.leaf_capacity,
            "arity": self.arity,
        }


def _positive_integer_environment(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def hierarchy_policy_from_environment() -> HierarchyExecutionPolicy:
    return HierarchyExecutionPolicy(
        leaf_capacity=_positive_integer_environment(
            "SENSIBLAW_HIERARCHY_LEAF_CAPACITY",
            4096,
        ),
        arity=_positive_integer_environment(
            "SENSIBLAW_HIERARCHY_ARITY",
            4,
        ),
    )


__all__ = [
    "HierarchyExecutionPolicy",
    "hierarchy_policy_from_environment",
]
