from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

EQUIVALENCE_ASSESSMENT_SCHEMA_VERSION = "sl.equivalence_assessment.v0_1"


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


@dataclass(frozen=True)
class EquivalenceAssessment:
    left_lane: str
    right_lane: str
    source_semantics_shared: bool
    target_semantics_shared: bool
    basis_vocabulary_shared: bool
    cardinality_shared: bool
    interpretation_shared: bool
    descriptive_only_shared: bool
    control_leakage_risk: bool
    notes: list[str]
    verdict: str
    schema_version: str = EQUIVALENCE_ASSESSMENT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "left_lane": self.left_lane,
            "right_lane": self.right_lane,
            "source_semantics_shared": self.source_semantics_shared,
            "target_semantics_shared": self.target_semantics_shared,
            "basis_vocabulary_shared": self.basis_vocabulary_shared,
            "cardinality_shared": self.cardinality_shared,
            "interpretation_shared": self.interpretation_shared,
            "descriptive_only_shared": self.descriptive_only_shared,
            "control_leakage_risk": self.control_leakage_risk,
            "notes": [note for note in self.notes if note],
            "verdict": self.verdict,
        }


def build_equivalence_assessment_dict(
    *,
    left_lane: str,
    right_lane: str,
    source_semantics_shared: bool,
    target_semantics_shared: bool,
    basis_vocabulary_shared: bool,
    cardinality_shared: bool,
    interpretation_shared: bool,
    descriptive_only_shared: bool,
    control_leakage_risk: bool,
    notes: list[str] | None = None,
    verdict: str,
) -> dict[str, Any]:
    return EquivalenceAssessment(
        left_lane=str(left_lane or "").strip(),
        right_lane=str(right_lane or "").strip(),
        source_semantics_shared=bool(source_semantics_shared),
        target_semantics_shared=bool(target_semantics_shared),
        basis_vocabulary_shared=bool(basis_vocabulary_shared),
        cardinality_shared=bool(cardinality_shared),
        interpretation_shared=bool(interpretation_shared),
        descriptive_only_shared=bool(descriptive_only_shared),
        control_leakage_risk=bool(control_leakage_risk),
        notes=list(notes or []),
        verdict=str(verdict or "").strip(),
    ).as_dict()
