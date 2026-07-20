from __future__ import annotations

from typing import Any, Mapping

from src.models.review_claim_record import (
    REVIEW_CANDIDATE_SCHEMA_VERSION,
    build_review_candidate_dict,
)


CANDIDATE_SURFACE_SCHEMA_VERSION = REVIEW_CANDIDATE_SCHEMA_VERSION


def build_candidate_surface(
    *,
    candidate_id: Any,
    candidate_kind: Any,
    source_kind: Any,
    selection_basis: Mapping[str, Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
    target_proposition_id: Any | None = None,
) -> dict[str, Any]:
    return build_review_candidate_dict(
        candidate_id=candidate_id,
        candidate_kind=candidate_kind,
        source_kind=source_kind,
        selection_basis=selection_basis,
        anchor_refs=anchor_refs,
        target_proposition_id=target_proposition_id,
    )


__all__ = [
    "CANDIDATE_SURFACE_SCHEMA_VERSION",
    "build_candidate_surface",
]
