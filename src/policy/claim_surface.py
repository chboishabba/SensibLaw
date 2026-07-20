from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.models.proposition_identity import (
    PROPOSITION_IDENTITY_SCHEMA_VERSION,
    build_proposition_identity_dict,
)
from src.models.proposition_relation import (
    PROPOSITION_RELATION_SCHEMA_VERSION,
    build_proposition_relation_dict,
)


CLAIM_IDENTITY_SURFACE_SCHEMA_VERSION = PROPOSITION_IDENTITY_SCHEMA_VERSION
CLAIM_RELATION_SURFACE_SCHEMA_VERSION = PROPOSITION_RELATION_SCHEMA_VERSION


def build_claim_identity_surface(
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
    return build_proposition_identity_dict(
        proposition_id=proposition_id,
        family_id=family_id,
        cohort_id=cohort_id,
        root_artifact_id=root_artifact_id,
        lane=lane,
        source_family=source_family,
        basis_kind=basis_kind,
        local_id=local_id,
        source_kind=source_kind,
        upstream_artifact_ids=upstream_artifact_ids,
        anchor_refs=anchor_refs,
    )


def build_claim_relation_surface(
    *,
    relation_id: Any,
    source_proposition_id: Any,
    target_proposition_id: Any,
    relation_kind: Any,
    evidence_status: Any = "review_only",
    source_kind: Any = "",
    upstream_artifact_ids: Sequence[Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_proposition_relation_dict(
        relation_id=relation_id,
        source_proposition_id=source_proposition_id,
        target_proposition_id=target_proposition_id,
        relation_kind=relation_kind,
        evidence_status=evidence_status,
        source_kind=source_kind,
        upstream_artifact_ids=upstream_artifact_ids,
        anchor_refs=anchor_refs,
    )


__all__ = [
    "CLAIM_IDENTITY_SURFACE_SCHEMA_VERSION",
    "CLAIM_RELATION_SURFACE_SCHEMA_VERSION",
    "build_claim_identity_surface",
    "build_claim_relation_surface",
]
