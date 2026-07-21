"""Granular review coordinates for proposals, factors, relations, subgraphs and builds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


REVIEW_COORDINATE_SCHEMA_VERSION = "sl.pnf.review_coordinate.v0_1"
_REVIEW_TARGET_KINDS = {
    "factor_proposal",
    "reduced_factor",
    "cross_document_relation",
    "subgraph",
    "semantic_build",
}
_REVIEW_STATES = {
    "supported",
    "supported_with_residuals",
    "unsupported",
    "contested",
    "unresolved",
    "not_reviewed",
}


@dataclass(frozen=True)
class SemanticReviewCoordinate:
    target_kind: str
    target_ref: str
    document_refs: tuple[str, ...]
    coordinate_refs: tuple[str, ...]
    review_dimension: str
    residuals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.target_kind not in _REVIEW_TARGET_KINDS:
            raise ValueError("unsupported semantic review target kind")
        if not self.target_ref:
            raise ValueError("target_ref is required")
        if not self.review_dimension:
            raise ValueError("review_dimension is required")

    @property
    def coordinate_ref(self) -> str:
        return "semantic-review-coordinate:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "target_kind": self.target_kind,
            "target_ref": self.target_ref,
            "document_refs": sorted(set(self.document_refs)),
            "coordinate_refs": sorted(set(self.coordinate_refs)),
            "review_dimension": self.review_dimension,
            "residuals": sorted(set(self.residuals)),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REVIEW_COORDINATE_SCHEMA_VERSION,
            "coordinate_ref": self.coordinate_ref,
            **self.identity_payload(),
            "semantic_state_mutated": False,
        }


@dataclass(frozen=True)
class SemanticReviewAssessment:
    coordinate_ref: str
    reviewer_credential_ref: str
    institution_ref: str
    review_state: str
    rationale_refs: tuple[str, ...]
    residuals: tuple[str, ...] = ()
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.review_state not in _REVIEW_STATES:
            raise ValueError("unsupported semantic review state")
        if not self.coordinate_ref or not self.reviewer_credential_ref:
            raise ValueError("coordinate and reviewer credential are required")

    @property
    def assessment_ref(self) -> str:
        return "semantic-review-assessment:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "coordinate_ref": self.coordinate_ref,
            "reviewer_credential_ref": self.reviewer_credential_ref,
            "institution_ref": self.institution_ref,
            "review_state": self.review_state,
            "rationale_refs": sorted(set(self.rationale_refs)),
            "residuals": sorted(set(self.residuals)),
            "metadata": dict(self.metadata or {}),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sl.pnf.review_assessment.v0_1",
            "assessment_ref": self.assessment_ref,
            **self.identity_payload(),
            "truth_closed": False,
            "semantic_state_promoted": False,
        }


def project_review_state(
    *,
    coordinate: SemanticReviewCoordinate,
    assessments: tuple[SemanticReviewAssessment, ...],
    accepted_credential_refs: tuple[str, ...] = (),
    accepted_institution_refs: tuple[str, ...] = (),
) -> dict[str, Any]:
    accepted_credentials = set(accepted_credential_refs)
    accepted_institutions = set(accepted_institution_refs)
    scoped = tuple(
        row
        for row in assessments
        if row.coordinate_ref == coordinate.coordinate_ref
        and (not accepted_credentials or row.reviewer_credential_ref in accepted_credentials)
        and (not accepted_institutions or row.institution_ref in accepted_institutions)
    )
    states = sorted({row.review_state for row in scoped})
    contested = "contested" in states or (
        any(state in {"supported", "supported_with_residuals"} for state in states)
        and "unsupported" in states
    )
    return {
        "schema_version": "sl.pnf.review_projection.v0_1",
        "coordinate_ref": coordinate.coordinate_ref,
        "assessment_refs": sorted(row.assessment_ref for row in scoped),
        "states": states,
        "contested": contested,
        "truth_closed": False,
        "semantic_state_promoted": False,
    }


__all__ = [
    "REVIEW_COORDINATE_SCHEMA_VERSION",
    "SemanticReviewAssessment",
    "SemanticReviewCoordinate",
    "project_review_state",
]
