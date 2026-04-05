from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROPOSITION_RELATION_SCHEMA_VERSION = "sl.proposition_relation.v0_1"


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
class PropositionRelation:
    relation_id: str
    source_proposition_id: str
    target_proposition_id: str
    relation_kind: str
    evidence_status: str
    provenance: dict[str, Any]
    schema_version: str = PROPOSITION_RELATION_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "relation_id": self.relation_id,
            "source_proposition_id": self.source_proposition_id,
            "target_proposition_id": self.target_proposition_id,
            "relation_kind": self.relation_kind,
            "evidence_status": self.evidence_status,
            "provenance": dict(self.provenance),
        }


def build_proposition_relation_dict(
    *,
    relation_id: Any,
    source_proposition_id: Any,
    target_proposition_id: Any,
    relation_kind: Any,
    evidence_status: Any = "review_only",
    source_kind: Any,
    upstream_artifact_ids: Sequence[Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return PropositionRelation(
        relation_id=_as_text(relation_id),
        source_proposition_id=_as_text(source_proposition_id),
        target_proposition_id=_as_text(target_proposition_id),
        relation_kind=_as_text(relation_kind),
        evidence_status=_as_text(evidence_status),
        provenance={
            "source_kind": _as_text(source_kind),
            "upstream_artifact_ids": _copy_text_list(upstream_artifact_ids),
            "anchor_refs": _copy_mapping(anchor_refs),
        },
    ).as_dict()
