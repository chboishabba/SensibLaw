"""Shared pressure envelope with separate coverage and closure semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.policy.carriers.canonical import canonical_refs, require_text


class PressureKind(str, Enum):
    COVERAGE = "coverage"
    CLOSURE = "closure"


@dataclass(frozen=True)
class PressureAssessment:
    target_ref: str
    pressure_kind: PressureKind | str
    state: str
    reasons: tuple[str, ...] = ()
    requested_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "target_ref": require_text(self.target_ref, "target_ref"),
            "pressure_kind": PressureKind(self.pressure_kind).value,
            "state": require_text(self.state, "pressure state"),
            "reasons": list(canonical_refs(self.reasons)),
            "requested_actions": list(canonical_refs(self.requested_actions)),
        }
