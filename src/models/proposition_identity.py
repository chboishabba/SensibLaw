from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROPOSITION_IDENTITY_SCHEMA_VERSION = "sl.proposition_identity.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _copy_text_list(values: Sequence[Any] | None) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [str(value) for value in values if isinstance(value, str) and str(value).strip()]


@dataclass(frozen=True)
class PropositionIdentity:
    proposition_id: str
    family_id: str
    cohort_id: str
    root_artifact_id: str
    lane: str
    source_family: str
    identity_basis: dict[str, Any]
    provenance: dict[str, Any]
    schema_version: str = PROPOSITION_IDENTITY_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposition_id": self.proposition_id,
            "family_id": self.family_id,
            "cohort_id": self.cohort_id,
            "root_artifact_id": self.root_artifact_id,
            "lane": self.lane,
            "source_family": self.source_family,
            "identity_basis": dict(self.identity_basis),
            "provenance": dict(self.provenance),
        }


def build_proposition_identity_dict(
    *,
    proposition_id: Any,
    family_id: Any,
    cohort_id: Any,
    root_artifact_id: Any,
    lane: Any,
    source_family: Any,
    basis_kind: Any,
    local_id: Any,
    source_kind: Any,
    upstream_artifact_ids: Sequence[Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return PropositionIdentity(
        proposition_id=_as_text(proposition_id),
        family_id=_as_text(family_id),
        cohort_id=_as_text(cohort_id),
        root_artifact_id=_as_text(root_artifact_id),
        lane=_as_text(lane),
        source_family=_as_text(source_family),
        identity_basis={
            "basis_kind": _as_text(basis_kind),
            "local_id": _as_text(local_id),
        },
        provenance={
            "source_kind": _as_text(source_kind),
            "upstream_artifact_ids": _copy_text_list(upstream_artifact_ids),
            "anchor_refs": _copy_mapping(anchor_refs),
        },
    ).as_dict()
