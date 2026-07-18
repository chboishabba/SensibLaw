"""Branch-preserving typed alternatives."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, Mapping, TypeVar

from src.policy.carriers.canonical import (
    canonical_mapping,
    canonical_refs,
    require_text,
)

T = TypeVar("T")


@dataclass(frozen=True)
class TypedAlternative(Generic[T]):
    alternative_ref: str
    value: T
    type_ref: str
    derivation_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    authority_state: str = "candidate_only"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        authority = require_text(self.authority_state, "authority_state")
        if authority not in {
            "candidate_only",
            "evidence_only",
            "assessment_only",
            "pnf_refinement_only",
        }:
            raise ValueError("typed alternatives cannot carry promotion authority")
        return {
            "alternative_ref": require_text(self.alternative_ref, "alternative_ref"),
            "value": self.value,
            "type_ref": require_text(self.type_ref, "type_ref"),
            "derivation_refs": list(canonical_refs(self.derivation_refs)),
            "evidence_refs": list(canonical_refs(self.evidence_refs)),
            "authority_state": authority,
            "metadata": canonical_mapping(self.metadata),
        }
