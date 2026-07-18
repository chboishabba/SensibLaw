"""Typed compatibility meets shared by entity, event, form, and PNF reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from src.policy.carriers.canonical import canonical_refs, require_text

M = TypeVar("M")


class MeetState(str, Enum):
    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_REFINEMENT = "compatible_with_refinement"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"
    NO_TYPED_MEET = "no_typed_meet"
    CONTRADICTION = "contradiction"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class TypedMeet(Generic[M]):
    meet_ref: str
    left_ref: str
    right_ref: str
    meet_type: str
    state: MeetState | str
    result_alternatives: tuple[M, ...] = ()
    refinement_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    residual_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        state = MeetState(self.state).value
        row: dict[str, object] = {
            "meet_ref": require_text(self.meet_ref, "meet_ref"),
            "left_ref": require_text(self.left_ref, "left_ref"),
            "right_ref": require_text(self.right_ref, "right_ref"),
            "meet_type": require_text(self.meet_type, "meet_type"),
            "state": state,
            "result_alternatives": list(self.result_alternatives),
            "evidence_refs": list(canonical_refs(self.evidence_refs)),
            "residual_refs": list(canonical_refs(self.residual_refs)),
            "authority": "assessment_only",
        }
        if self.refinement_ref:
            row["refinement_ref"] = require_text(
                self.refinement_ref, "refinement_ref"
            )
        if state in {MeetState.NO_TYPED_MEET.value, MeetState.CONTRADICTION.value} and self.result_alternatives:
            raise ValueError("failed typed meets cannot emit result alternatives")
        return row
