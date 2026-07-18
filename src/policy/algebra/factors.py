"""Immutable factors shared by PNF, entity, event, and reference compilation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Generic, Mapping, TypeVar

from src.policy.carriers.canonical import (
    canonical_mapping,
    canonical_refs,
    require_text,
)

from .alternatives import TypedAlternative

T = TypeVar("T")

_CLOSURE_STATES = {
    "open",
    "locally_closed",
    "closed",
    "requires_local_typing",
    "requires_external_resolution",
    "not_required",
}


@dataclass(frozen=True)
class FactorConstraint:
    constraint_ref: str
    constraint_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    provenance_refs: tuple[str, ...] = ()
    source_factor_refs: tuple[str, ...] = ()
    target_factor_refs: tuple[str, ...] = ()
    alternative_group: str | None = None
    required: bool = True
    residual_on_failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_ref": require_text(self.constraint_ref, "constraint_ref"),
            "constraint_type": require_text(self.constraint_type, "constraint_type"),
            "payload": canonical_mapping(self.payload),
            "provenance_refs": list(canonical_refs(self.provenance_refs)),
            "source_factor_refs": list(canonical_refs(self.source_factor_refs)),
            "target_factor_refs": list(canonical_refs(self.target_factor_refs)),
            "alternative_group": self.alternative_group,
            "required": self.required,
            "residual_on_failure": self.residual_on_failure,
        }


@dataclass(frozen=True)
class Factor(Generic[T]):
    factor_ref: str
    factor_type: str
    alternatives: tuple[TypedAlternative[T], ...] = ()
    constraints: tuple[FactorConstraint, ...] = ()
    residuals: tuple[str, ...] = ()
    closure_state: str = "open"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.factor_ref, "factor_ref")
        require_text(self.factor_type, "factor_type")
        if self.closure_state not in _CLOSURE_STATES:
            raise ValueError(f"unsupported factor closure state: {self.closure_state}")
        refs = [item.alternative_ref for item in self.alternatives]
        if len(refs) != len(set(refs)):
            raise ValueError("factor alternatives require unique references")

    def to_dict(self) -> dict[str, Any]:
        alternatives = sorted(
            (item.to_dict() for item in self.alternatives),
            key=lambda row: row["alternative_ref"],
        )
        constraints = sorted(
            (item.to_dict() for item in self.constraints),
            key=lambda row: row["constraint_ref"],
        )
        return {
            "factor_ref": self.factor_ref,
            "factor_type": self.factor_type,
            "alternatives": alternatives,
            "constraints": constraints,
            "residuals": list(canonical_refs(self.residuals)),
            "closure_state": self.closure_state,
            "metadata": canonical_mapping(self.metadata),
        }

    def add_alternatives(self, *alternatives: TypedAlternative[T]) -> "Factor[T]":
        by_ref = {item.alternative_ref: item for item in self.alternatives}
        for item in alternatives:
            existing = by_ref.get(item.alternative_ref)
            if existing is not None and existing.to_dict() != item.to_dict():
                raise ValueError(
                    "cannot replace an alternative through add_alternatives"
                )
            by_ref[item.alternative_ref] = item
        return replace(self, alternatives=tuple(by_ref[key] for key in sorted(by_ref)))

    def retain_alternatives(self, refs: tuple[str, ...]) -> "Factor[T]":
        retained = set(canonical_refs(refs))
        unknown = retained.difference(
            item.alternative_ref for item in self.alternatives
        )
        if unknown:
            raise ValueError(f"cannot retain unknown alternatives: {sorted(unknown)}")
        return replace(
            self,
            alternatives=tuple(
                item for item in self.alternatives if item.alternative_ref in retained
            ),
        )

    def reject_alternatives(self, refs: tuple[str, ...]) -> "Factor[T]":
        rejected = set(canonical_refs(refs))
        return replace(
            self,
            alternatives=tuple(
                item
                for item in self.alternatives
                if item.alternative_ref not in rejected
            ),
        )

    def transition_residuals(
        self,
        *,
        remove: tuple[str, ...] = (),
        add: tuple[str, ...] = (),
        closure_state: str | None = None,
    ) -> "Factor[T]":
        residuals = set(self.residuals)
        residuals.difference_update(canonical_refs(remove))
        residuals.update(canonical_refs(add))
        next_state = closure_state or self.closure_state
        return replace(
            self,
            residuals=tuple(sorted(residuals)),
            closure_state=next_state,
        )
