from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LANE_SEMANTICS_PROFILE_SCHEMA_VERSION = "sl.lane_semantics_profile.v0_1"


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


@dataclass(frozen=True)
class LaneSemanticsProfile:
    lane: str
    family_id: str
    origin_kinds: list[str]
    target_kinds: list[str]
    cardinality_mode: str
    basis_vocabulary: list[str]
    interpretation_kind: str
    descriptive_only: bool
    control_leakage_risk: bool
    relation_kinds: list[str]
    text_roles: list[str]
    anchor_ref_keys: list[str]
    semantic_notes: list[str]
    schema_version: str = LANE_SEMANTICS_PROFILE_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "lane": self.lane,
            "family_id": self.family_id,
            "origin_kinds": _sorted_unique(list(self.origin_kinds)),
            "target_kinds": _sorted_unique(list(self.target_kinds)),
            "cardinality_mode": self.cardinality_mode,
            "basis_vocabulary": _sorted_unique(list(self.basis_vocabulary)),
            "interpretation_kind": self.interpretation_kind,
            "descriptive_only": self.descriptive_only,
            "control_leakage_risk": self.control_leakage_risk,
            "relation_kinds": _sorted_unique(list(self.relation_kinds)),
            "text_roles": _sorted_unique(list(self.text_roles)),
            "anchor_ref_keys": _sorted_unique(list(self.anchor_ref_keys)),
            "semantic_notes": [note for note in self.semantic_notes if note],
        }


def build_lane_semantics_profile_dict(
    *,
    lane: str,
    family_id: str,
    origin_kinds: list[str],
    target_kinds: list[str],
    cardinality_mode: str,
    basis_vocabulary: list[str],
    interpretation_kind: str,
    descriptive_only: bool,
    control_leakage_risk: bool,
    relation_kinds: list[str] | None = None,
    text_roles: list[str] | None = None,
    anchor_ref_keys: list[str] | None = None,
    semantic_notes: list[str] | None = None,
) -> dict[str, Any]:
    return LaneSemanticsProfile(
        lane=str(lane or "").strip(),
        family_id=str(family_id or "").strip(),
        origin_kinds=_sorted_unique(list(origin_kinds or [])),
        target_kinds=_sorted_unique(list(target_kinds or [])),
        cardinality_mode=str(cardinality_mode or "").strip(),
        basis_vocabulary=_sorted_unique(list(basis_vocabulary or [])),
        interpretation_kind=str(interpretation_kind or "").strip(),
        descriptive_only=bool(descriptive_only),
        control_leakage_risk=bool(control_leakage_risk),
        relation_kinds=_sorted_unique(list(relation_kinds or [])),
        text_roles=_sorted_unique(list(text_roles or [])),
        anchor_ref_keys=_sorted_unique(list(anchor_ref_keys or [])),
        semantic_notes=list(semantic_notes or []),
    ).as_dict()
