from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


NAT_CLAIM_SCHEMA_VERSION = "sl.wikidata_nat_claim.v0_1"


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


def _normalize_claim_bundle(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    normalized = {str(key): item for key, item in value.items()}
    qualifiers = value.get("qualifiers", {})
    references = value.get("references", [])
    normalized_references: list[dict[str, Any]] = []
    if isinstance(references, list):
        normalized_references = [
            _copy_mapping(reference) for reference in references if isinstance(reference, Mapping)
        ]
    normalized["subject"] = _as_text(value.get("subject"))
    normalized["property"] = _as_text(value.get("property"))
    normalized["value"] = _as_text(value.get("value"))
    normalized["rank"] = _as_text(value.get("rank"))
    normalized["window_id"] = _as_text(value.get("window_id"))
    normalized["qualifiers"] = _copy_mapping(qualifiers)
    normalized["references"] = normalized_references
    return normalized


@dataclass(frozen=True)
class NatClaim:
    claim_id: str
    family_id: str
    cohort_id: str
    candidate_id: str
    subject: str
    predicate: str
    obj: str
    source_property: str
    target_property: str
    state: str
    state_basis: str
    root_artifact_id: str
    canonical_form: dict[str, Any]
    provenance: dict[str, Any]
    evidence_status: str
    schema_version: str = NAT_CLAIM_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        canonical_form = dict(self.canonical_form)
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "family_id": self.family_id,
            "cohort_id": self.cohort_id,
            "candidate_id": self.candidate_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.obj,
            "source_property": self.source_property,
            "target_property": self.target_property,
            "state": self.state,
            "state_basis": self.state_basis,
            "root_artifact_id": self.root_artifact_id,
            "canonical_form": canonical_form,
            "subject": _as_text(canonical_form.get("subject")) or self.subject,
            "property": _as_text(canonical_form.get("property")) or self.predicate,
            "value": _as_text(canonical_form.get("value")) or self.obj,
            "rank": _as_text(canonical_form.get("rank")),
            "window_id": _as_text(canonical_form.get("window_id")),
            "qualifiers": _copy_mapping(canonical_form.get("qualifiers")),
            "references": list(canonical_form.get("references", []))
            if isinstance(canonical_form.get("references"), list)
            else [],
            "provenance": dict(self.provenance),
            "evidence_status": self.evidence_status,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.as_dict()


NormalizedClaim = NatClaim


def build_nat_claim_dict(
    *,
    claim_id: str,
    family_id: str,
    cohort_id: str,
    candidate_id: str,
    canonical_form: Mapping[str, Any],
    source_property: str,
    target_property: str,
    state: str,
    state_basis: str,
    root_artifact_id: str,
    provenance: Mapping[str, Any] | None = None,
    evidence_status: str,
) -> dict[str, Any]:
    normalized_form = _normalize_claim_bundle(canonical_form)
    claim = NatClaim(
        claim_id=_as_text(claim_id),
        family_id=_as_text(family_id),
        cohort_id=_as_text(cohort_id),
        candidate_id=_as_text(candidate_id),
        subject=_as_text(normalized_form.get("subject")),
        predicate=_as_text(normalized_form.get("property")),
        obj=_as_text(normalized_form.get("value")),
        source_property=_as_text(source_property),
        target_property=_as_text(target_property),
        state=_as_text(state),
        state_basis=_as_text(state_basis),
        root_artifact_id=_as_text(root_artifact_id),
        canonical_form=normalized_form,
        provenance=_copy_mapping(provenance),
        evidence_status=_as_text(evidence_status),
    )
    return claim.as_dict()


def build_nat_claim_from_candidate(candidate: Mapping[str, Any]) -> NatClaim:
    canonical_form = _normalize_claim_bundle(
        candidate.get("claim_bundle_after") if isinstance(candidate, Mapping) else {}
    )
    if not canonical_form:
        canonical_form = _normalize_claim_bundle(
            candidate.get("claim_bundle_before") if isinstance(candidate, Mapping) else {}
        )
    candidate_id = _as_text(candidate.get("candidate_id")) if isinstance(candidate, Mapping) else ""
    subject = _as_text(canonical_form.get("subject"))
    predicate = _as_text(canonical_form.get("property"))
    obj = _as_text(canonical_form.get("value"))
    return NatClaim(
        claim_id=candidate_id,
        family_id=_as_text(candidate.get("family_id")) if isinstance(candidate, Mapping) else "",
        cohort_id=_as_text(candidate.get("cohort_id")) if isinstance(candidate, Mapping) else "",
        candidate_id=candidate_id,
        subject=subject,
        predicate=predicate,
        obj=obj,
        source_property=_as_text(
            _normalize_claim_bundle(candidate.get("claim_bundle_before")).get("property")
        )
        if isinstance(candidate, Mapping)
        else predicate,
        target_property=predicate,
        state=_as_text(candidate.get("status")) if isinstance(candidate, Mapping) and candidate.get("status") else "candidate",
        state_basis=_as_text(candidate.get("state_basis"))
        if isinstance(candidate, Mapping) and candidate.get("state_basis")
        else "baseline_runtime",
        root_artifact_id=_as_text(candidate.get("root_artifact_id")) if isinstance(candidate, Mapping) else "",
        canonical_form=canonical_form,
        provenance={"source_kind": _as_text(candidate.get("source_kind"))}
        if isinstance(candidate, Mapping) and candidate.get("source_kind")
        else {},
        evidence_status="single_run",
    )


def build_normalized_claim_dict(**kwargs: Any) -> dict[str, Any]:
    return build_nat_claim_dict(**kwargs)


def build_normalized_claim_from_candidate(candidate: Mapping[str, Any]) -> NormalizedClaim:
    return build_nat_claim_from_candidate(candidate)
