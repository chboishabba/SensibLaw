from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .proposition_identity import build_proposition_identity_dict

REVIEW_CANDIDATE_SCHEMA_VERSION = "sl.review_candidate.v0_1"
REVIEW_CLAIM_RECORD_SCHEMA_VERSION = "sl.review_claim_record.v0_4"


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


@dataclass(frozen=True)
class ReviewClaimRecord:
    claim_id: str
    candidate_id: str
    family_id: str
    cohort_id: str
    root_artifact_id: str
    lane: str
    source_family: str
    state: str
    state_basis: str
    evidence_status: str
    proposition_identity: dict[str, Any]
    review_candidate: dict[str, Any] | None
    target_proposition_identity: dict[str, Any] | None
    proposition_relation: dict[str, Any] | None
    review_text: dict[str, Any] | None
    provenance: dict[str, Any]
    decision_basis: dict[str, Any]
    review_route: dict[str, Any]
    schema_version: str = REVIEW_CLAIM_RECORD_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "cohort_id": self.cohort_id,
            "root_artifact_id": self.root_artifact_id,
            "lane": self.lane,
            "source_family": self.source_family,
            "state": self.state,
            "state_basis": self.state_basis,
            "evidence_status": self.evidence_status,
            "proposition_identity": dict(self.proposition_identity),
        }
        if isinstance(self.review_candidate, Mapping) and self.review_candidate:
            payload["review_candidate"] = dict(self.review_candidate)
        if isinstance(self.target_proposition_identity, Mapping) and self.target_proposition_identity:
            payload["target_proposition_identity"] = dict(self.target_proposition_identity)
        if isinstance(self.proposition_relation, Mapping) and self.proposition_relation:
            payload["proposition_relation"] = dict(self.proposition_relation)
        if isinstance(self.review_text, Mapping) and self.review_text:
            payload["review_text"] = dict(self.review_text)
        payload["provenance"] = dict(self.provenance)
        payload["decision_basis"] = dict(self.decision_basis)
        payload["review_route"] = dict(self.review_route)
        return payload


def build_review_claim_record_dict(
    *,
    claim_id: Any,
    candidate_id: Any,
    family_id: Any,
    cohort_id: Any,
    root_artifact_id: Any,
    lane: Any,
    source_family: Any,
    state: Any,
    state_basis: Any,
    evidence_status: Any,
    proposition_identity: Mapping[str, Any] | None = None,
    review_candidate: Mapping[str, Any] | None = None,
    target_proposition_identity: Mapping[str, Any] | None = None,
    proposition_relation: Mapping[str, Any] | None = None,
    review_text: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
    decision_basis: Mapping[str, Any] | None = None,
    review_route: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity_mapping = _copy_mapping(proposition_identity)
    if not identity_mapping:
        identity_mapping = build_proposition_identity_dict(
            proposition_id=claim_id,
            family_id=family_id,
            cohort_id=cohort_id,
            root_artifact_id=root_artifact_id,
            lane=lane,
            source_family=source_family,
            basis_kind="review_claim_record",
            local_id=claim_id,
            source_kind="review_claim_record",
            upstream_artifact_ids=[root_artifact_id, cohort_id],
            anchor_refs={"claim_id": _as_text(claim_id), "candidate_id": _as_text(candidate_id)},
        )
    return ReviewClaimRecord(
        claim_id=_as_text(claim_id),
        candidate_id=_as_text(candidate_id),
        family_id=_as_text(family_id),
        cohort_id=_as_text(cohort_id),
        root_artifact_id=_as_text(root_artifact_id),
        lane=_as_text(lane),
        source_family=_as_text(source_family),
        state=_as_text(state),
        state_basis=_as_text(state_basis),
        evidence_status=_as_text(evidence_status),
        proposition_identity=identity_mapping,
        review_candidate=_copy_mapping(review_candidate) or None,
        target_proposition_identity=_copy_mapping(target_proposition_identity) or None,
        proposition_relation=_copy_mapping(proposition_relation) or None,
        review_text=_copy_mapping(review_text) or None,
        provenance=_copy_mapping(provenance),
        decision_basis=_copy_mapping(decision_basis),
        review_route=_copy_mapping(review_route),
    ).as_dict()


def build_review_candidate_dict(
    *,
    candidate_id: Any,
    candidate_kind: Any,
    source_kind: Any,
    selection_basis: Mapping[str, Any] | None = None,
    anchor_refs: Mapping[str, Any] | None = None,
    target_proposition_id: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": REVIEW_CANDIDATE_SCHEMA_VERSION,
        "candidate_id": _as_text(candidate_id),
        "candidate_kind": _as_text(candidate_kind),
        "source_kind": _as_text(source_kind),
        "selection_basis": _copy_mapping(selection_basis),
    }
    clean_anchor_refs = _copy_mapping(anchor_refs)
    clean_anchor_refs = {
        str(key): value
        for key, value in clean_anchor_refs.items()
        if value not in (None, "", [], {})
    }
    if clean_anchor_refs:
        payload["anchor_refs"] = clean_anchor_refs
    target_value = _as_text(target_proposition_id)
    if target_value:
        payload["target_proposition_id"] = target_value
    return payload
