"""Federated review and trust algebra for the Legal IR product.

The federation layer does not alter PNF or Legal IR observations. It records
attributable review acts over immutable graph revisions and derives scoped trust
projections without collapsing disagreement or turning popularity into truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256

LEGAL_IR_FEDERATION_CONTRACT = "legal-ir-federation:v0_1"
LEGAL_IR_ATTESTATION_CONTRACT = "legal-ir-attestation:v0_1"
LEGAL_IR_TRUST_PROJECTION_CONTRACT = "legal-ir-trust-projection:v0_1"

_REVIEW_STATES = frozenset(
    {
        "endorse",
        "approve_with_residuals",
        "reject",
        "contest",
        "abstain",
        "supersede",
    }
)


@dataclass(frozen=True)
class LegalGraphRevision:
    revision_ref: str
    subject_ref: str
    payload_hash: str
    prior_revision_refs: tuple[str, ...]
    source_span_refs: tuple[str, ...]
    legal_system_refs: tuple[str, ...]
    jurisdiction_refs: tuple[str, ...]
    temporal_refs: tuple[str, ...]
    author_ref: str
    institution_ref: str | None
    build_ref: str
    revision_state: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "authority": "candidate_graph_revision",
            "mutable": False,
        }


@dataclass(frozen=True)
class ReviewerCredential:
    credential_ref: str
    reviewer_ref: str
    institution_ref: str | None
    jurisdiction_refs: tuple[str, ...]
    practice_area_refs: tuple[str, ...]
    credential_type_refs: tuple[str, ...]
    valid_from: str | None
    valid_until: str | None
    evidence_refs: tuple[str, ...]
    verification_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "authority": "credential_evidence_only",
            "confers_truth_authority": False,
        }


@dataclass(frozen=True)
class LegalReviewAttestation:
    attestation_ref: str
    revision_ref: str
    reviewer_ref: str
    credential_refs: tuple[str, ...]
    institution_ref: str | None
    review_state: str
    coordinate_states: Mapping[str, str]
    reason_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    supersedes_attestation_refs: tuple[str, ...]
    created_at: str
    signature_ref: str | None = None

    def __post_init__(self) -> None:
        if self.review_state not in _REVIEW_STATES:
            raise ValueError(f"unsupported legal review state: {self.review_state}")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "coordinate_states": dict(self.coordinate_states),
            "contract_ref": LEGAL_IR_ATTESTATION_CONTRACT,
            "authority": "attributed_review_act",
            "changes_graph_revision": False,
        }


@dataclass(frozen=True)
class FederatedClaimState:
    revision_ref: str
    scope_ref: str
    endorsement_count: int
    qualified_approval_count: int
    rejection_count: int
    contest_count: int
    abstention_count: int
    supersession_count: int
    active_reviewer_refs: tuple[str, ...]
    institution_refs: tuple[str, ...]
    unresolved_coordinate_refs: tuple[str, ...]
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": LEGAL_IR_TRUST_PROJECTION_CONTRACT,
            "authority": "scoped_review_projection_only",
            "truth_closed": False,
        }


@dataclass(frozen=True)
class FederationBundle:
    bundle_ref: str
    graph_revision_refs: tuple[str, ...]
    credential_refs: tuple[str, ...]
    attestation_refs: tuple[str, ...]
    trust_projection_refs: tuple[str, ...]
    federation_refs: tuple[str, ...]
    checkpoint_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": LEGAL_IR_FEDERATION_CONTRACT,
            "authority": "federated_review_surface",
            "anonymous_consensus": False,
            "disagreement_preserved": True,
        }


def create_graph_revision(
    *,
    subject_ref: str,
    payload: Mapping[str, Any],
    prior_revision_refs: Iterable[str] = (),
    source_span_refs: Iterable[str] = (),
    legal_system_refs: Iterable[str] = (),
    jurisdiction_refs: Iterable[str] = (),
    temporal_refs: Iterable[str] = (),
    author_ref: str,
    institution_ref: str | None,
    build_ref: str,
) -> LegalGraphRevision:
    payload_hash = canonical_sha256(dict(payload))
    identity = {
        "contract": LEGAL_IR_FEDERATION_CONTRACT,
        "subject_ref": subject_ref,
        "payload_hash": payload_hash,
        "prior_revision_refs": sorted(set(prior_revision_refs)),
        "author_ref": author_ref,
        "institution_ref": institution_ref,
        "build_ref": build_ref,
    }
    return LegalGraphRevision(
        revision_ref="legal-graph-revision:" + canonical_sha256(identity),
        subject_ref=subject_ref,
        payload_hash=payload_hash,
        prior_revision_refs=tuple(sorted(set(prior_revision_refs))),
        source_span_refs=tuple(sorted(set(source_span_refs))),
        legal_system_refs=tuple(sorted(set(legal_system_refs))),
        jurisdiction_refs=tuple(sorted(set(jurisdiction_refs))),
        temporal_refs=tuple(sorted(set(temporal_refs))),
        author_ref=author_ref,
        institution_ref=institution_ref,
        build_ref=build_ref,
    )


def create_review_attestation(
    *,
    revision_ref: str,
    reviewer_ref: str,
    credential_refs: Iterable[str],
    institution_ref: str | None,
    review_state: str,
    coordinate_states: Mapping[str, str],
    reason_refs: Iterable[str],
    evidence_refs: Iterable[str],
    supersedes_attestation_refs: Iterable[str],
    created_at: str,
    signature_ref: str | None = None,
) -> LegalReviewAttestation:
    identity = {
        "contract": LEGAL_IR_ATTESTATION_CONTRACT,
        "revision_ref": revision_ref,
        "reviewer_ref": reviewer_ref,
        "credential_refs": sorted(set(credential_refs)),
        "institution_ref": institution_ref,
        "review_state": review_state,
        "coordinate_states": dict(sorted(coordinate_states.items())),
        "reason_refs": sorted(set(reason_refs)),
        "evidence_refs": sorted(set(evidence_refs)),
        "supersedes": sorted(set(supersedes_attestation_refs)),
        "created_at": created_at,
        "signature_ref": signature_ref,
    }
    return LegalReviewAttestation(
        attestation_ref="legal-review-attestation:" + canonical_sha256(identity),
        revision_ref=revision_ref,
        reviewer_ref=reviewer_ref,
        credential_refs=tuple(sorted(set(credential_refs))),
        institution_ref=institution_ref,
        review_state=review_state,
        coordinate_states=dict(coordinate_states),
        reason_refs=tuple(sorted(set(reason_refs))),
        evidence_refs=tuple(sorted(set(evidence_refs))),
        supersedes_attestation_refs=tuple(sorted(set(supersedes_attestation_refs))),
        created_at=created_at,
        signature_ref=signature_ref,
    )


def _active_attestations(
    attestations: Sequence[LegalReviewAttestation],
) -> tuple[LegalReviewAttestation, ...]:
    superseded = {
        ref
        for row in attestations
        for ref in row.supersedes_attestation_refs
    }
    return tuple(row for row in attestations if row.attestation_ref not in superseded)


def project_federated_claim_state(
    *,
    revision_ref: str,
    attestations: Sequence[LegalReviewAttestation],
    scope_ref: str = "scope:global-unweighted",
    accepted_credential_refs: Iterable[str] = (),
    accepted_institution_refs: Iterable[str] = (),
) -> FederatedClaimState:
    accepted_credentials = set(accepted_credential_refs)
    accepted_institutions = set(accepted_institution_refs)
    scoped: list[LegalReviewAttestation] = []
    for row in _active_attestations(attestations):
        if row.revision_ref != revision_ref:
            continue
        if accepted_credentials and not accepted_credentials.intersection(row.credential_refs):
            continue
        if accepted_institutions and row.institution_ref not in accepted_institutions:
            continue
        scoped.append(row)
    counts = {state: 0 for state in _REVIEW_STATES}
    unresolved: set[str] = set()
    for row in scoped:
        counts[row.review_state] += 1
        unresolved.update(
            coordinate
            for coordinate, state in row.coordinate_states.items()
            if state in {"unresolved", "contested", "insufficient_evidence"}
        )
    if counts["supersede"]:
        state = "supersession_proposed"
    elif counts["reject"] and (counts["endorse"] or counts["approve_with_residuals"]):
        state = "contested"
    elif counts["contest"]:
        state = "contested"
    elif counts["reject"] and not counts["endorse"]:
        state = "rejected_in_scope"
    elif counts["endorse"]:
        state = "endorsed_in_scope"
    elif counts["approve_with_residuals"]:
        state = "approved_with_residuals_in_scope"
    else:
        state = "unreviewed_in_scope"
    return FederatedClaimState(
        revision_ref=revision_ref,
        scope_ref=scope_ref,
        endorsement_count=counts["endorse"],
        qualified_approval_count=counts["approve_with_residuals"],
        rejection_count=counts["reject"],
        contest_count=counts["contest"],
        abstention_count=counts["abstain"],
        supersession_count=counts["supersede"],
        active_reviewer_refs=tuple(sorted({row.reviewer_ref for row in scoped})),
        institution_refs=tuple(sorted({row.institution_ref for row in scoped if row.institution_ref})),
        unresolved_coordinate_refs=tuple(sorted(unresolved)),
        state=state,
    )


def build_federation_bundle(
    *,
    revisions: Sequence[LegalGraphRevision],
    credentials: Sequence[ReviewerCredential],
    attestations: Sequence[LegalReviewAttestation],
    projections: Sequence[FederatedClaimState],
    federation_refs: Iterable[str] = (),
) -> FederationBundle:
    identity = {
        "contract": LEGAL_IR_FEDERATION_CONTRACT,
        "revisions": [row.revision_ref for row in revisions],
        "credentials": [row.credential_ref for row in credentials],
        "attestations": [row.attestation_ref for row in attestations],
        "projections": [canonical_sha256(row.to_dict()) for row in projections],
        "federations": sorted(set(federation_refs)),
    }
    return FederationBundle(
        bundle_ref="legal-ir-federation-bundle:" + canonical_sha256(identity),
        graph_revision_refs=tuple(sorted(row.revision_ref for row in revisions)),
        credential_refs=tuple(sorted(row.credential_ref for row in credentials)),
        attestation_refs=tuple(sorted(row.attestation_ref for row in attestations)),
        trust_projection_refs=tuple(
            sorted("legal-trust-projection:" + canonical_sha256(row.to_dict()) for row in projections)
        ),
        federation_refs=tuple(sorted(set(federation_refs))),
        checkpoint_state="reviewable_federated_graph",
    )


__all__ = [
    "LEGAL_IR_FEDERATION_CONTRACT",
    "FederatedClaimState",
    "FederationBundle",
    "LegalGraphRevision",
    "LegalReviewAttestation",
    "ReviewerCredential",
    "build_federation_bundle",
    "create_graph_revision",
    "create_review_attestation",
    "project_federated_claim_state",
]
