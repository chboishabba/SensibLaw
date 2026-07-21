"""System and subgraph review algebra for the federated Legal IR product.

A reviewer may assess not only atomic coordinates but whether SensibLaw/ITIR has
identified the right legal object, placed it correctly in the graph, assigned the
right functions and outcomes, and derived defensible implications.  These acts are
attributable review evidence; they never close legal truth or mutate PNF directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256

LEGAL_SYSTEM_REVIEW_CONTRACT = "legal-ir-system-review:v0_1"
LEGAL_SYSTEM_REVIEW_PROJECTION_CONTRACT = "legal-ir-system-review-projection:v0_1"

_REVIEW_STATES = frozenset(
    {"endorse", "approve_with_residuals", "reject", "contest", "abstain", "supersede"}
)
_CLAIM_KINDS = frozenset(
    {
        "identification",
        "graph_placement",
        "structural_role",
        "legal_function",
        "legal_outcome",
        "legal_implication",
        "cross_source_join",
        "temporal_validity",
        "jurisdictional_scope",
        "reconstruction_fitness",
        "subgraph_coherence",
        "build_fitness",
    }
)
_CLAIM_STATES = frozenset(
    {"supported", "supported_with_residuals", "unsupported", "contested", "unresolved", "not_reviewed"}
)


@dataclass(frozen=True)
class LegalReviewClaim:
    claim_ref: str
    claim_kind: str
    subject_ref: str
    proposition_ref: str
    target_refs: tuple[str, ...]
    source_span_refs: tuple[str, ...]
    dependency_claim_refs: tuple[str, ...]
    residual_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.claim_kind not in _CLAIM_KINDS:
            raise ValueError(f"unsupported legal review claim kind: {self.claim_kind}")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": LEGAL_SYSTEM_REVIEW_CONTRACT,
            "authority": "reviewable_claim_only",
            "truth_closed": False,
        }


@dataclass(frozen=True)
class LegalSystemReviewAttestation:
    attestation_ref: str
    revision_ref: str
    build_ref: str
    reviewer_ref: str
    credential_refs: tuple[str, ...]
    institution_ref: str | None
    review_state: str
    claim_states: Mapping[str, str]
    reviewed_claim_refs: tuple[str, ...]
    reason_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    method_refs: tuple[str, ...]
    supersedes_attestation_refs: tuple[str, ...]
    created_at: str
    signature_ref: str | None = None

    def __post_init__(self) -> None:
        if self.review_state not in _REVIEW_STATES:
            raise ValueError(f"unsupported legal review state: {self.review_state}")
        unsupported = {state for state in self.claim_states.values() if state not in _CLAIM_STATES}
        if unsupported:
            raise ValueError(f"unsupported legal claim states: {sorted(unsupported)}")
        if set(self.claim_states) - set(self.reviewed_claim_refs):
            raise ValueError("claim_states must be scoped to reviewed_claim_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "claim_states": dict(self.claim_states),
            "contract_ref": LEGAL_SYSTEM_REVIEW_CONTRACT,
            "authority": "attributed_system_review_act",
            "changes_graph_revision": False,
            "changes_pnf": False,
            "truth_closed": False,
        }


@dataclass(frozen=True)
class LegalSystemReviewProjection:
    revision_ref: str
    build_ref: str
    scope_ref: str
    active_attestation_refs: tuple[str, ...]
    supported_claim_refs: tuple[str, ...]
    qualified_claim_refs: tuple[str, ...]
    unsupported_claim_refs: tuple[str, ...]
    contested_claim_refs: tuple[str, ...]
    unresolved_claim_refs: tuple[str, ...]
    reviewer_refs: tuple[str, ...]
    institution_refs: tuple[str, ...]
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": LEGAL_SYSTEM_REVIEW_PROJECTION_CONTRACT,
            "authority": "scoped_review_projection_only",
            "truth_closed": False,
            "universal_authority": False,
        }


def create_review_claim(
    *,
    claim_kind: str,
    subject_ref: str,
    proposition_ref: str,
    target_refs: Iterable[str] = (),
    source_span_refs: Iterable[str] = (),
    dependency_claim_refs: Iterable[str] = (),
    residual_refs: Iterable[str] = (),
) -> LegalReviewClaim:
    identity = {
        "contract": LEGAL_SYSTEM_REVIEW_CONTRACT,
        "claim_kind": claim_kind,
        "subject_ref": subject_ref,
        "proposition_ref": proposition_ref,
        "target_refs": sorted(set(target_refs)),
        "source_span_refs": sorted(set(source_span_refs)),
        "dependencies": sorted(set(dependency_claim_refs)),
    }
    return LegalReviewClaim(
        claim_ref="legal-review-claim:" + canonical_sha256(identity),
        claim_kind=claim_kind,
        subject_ref=subject_ref,
        proposition_ref=proposition_ref,
        target_refs=tuple(sorted(set(target_refs))),
        source_span_refs=tuple(sorted(set(source_span_refs))),
        dependency_claim_refs=tuple(sorted(set(dependency_claim_refs))),
        residual_refs=tuple(sorted(set(residual_refs))),
    )


def create_system_review_attestation(
    *,
    revision_ref: str,
    build_ref: str,
    reviewer_ref: str,
    credential_refs: Iterable[str],
    institution_ref: str | None,
    review_state: str,
    claim_states: Mapping[str, str],
    reason_refs: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
    method_refs: Iterable[str] = (),
    supersedes_attestation_refs: Iterable[str] = (),
    created_at: str,
    signature_ref: str | None = None,
) -> LegalSystemReviewAttestation:
    reviewed_claim_refs = tuple(sorted(claim_states))
    identity = {
        "contract": LEGAL_SYSTEM_REVIEW_CONTRACT,
        "revision_ref": revision_ref,
        "build_ref": build_ref,
        "reviewer_ref": reviewer_ref,
        "credential_refs": sorted(set(credential_refs)),
        "institution_ref": institution_ref,
        "review_state": review_state,
        "claim_states": dict(sorted(claim_states.items())),
        "reasons": sorted(set(reason_refs)),
        "evidence": sorted(set(evidence_refs)),
        "methods": sorted(set(method_refs)),
        "supersedes": sorted(set(supersedes_attestation_refs)),
        "created_at": created_at,
        "signature_ref": signature_ref,
    }
    return LegalSystemReviewAttestation(
        attestation_ref="legal-system-review-attestation:" + canonical_sha256(identity),
        revision_ref=revision_ref,
        build_ref=build_ref,
        reviewer_ref=reviewer_ref,
        credential_refs=tuple(sorted(set(credential_refs))),
        institution_ref=institution_ref,
        review_state=review_state,
        claim_states=dict(claim_states),
        reviewed_claim_refs=reviewed_claim_refs,
        reason_refs=tuple(sorted(set(reason_refs))),
        evidence_refs=tuple(sorted(set(evidence_refs))),
        method_refs=tuple(sorted(set(method_refs))),
        supersedes_attestation_refs=tuple(sorted(set(supersedes_attestation_refs))),
        created_at=created_at,
        signature_ref=signature_ref,
    )


def project_system_review(
    *,
    revision_ref: str,
    build_ref: str,
    attestations: Sequence[LegalSystemReviewAttestation],
    scope_ref: str = "scope:global-unweighted",
    accepted_credential_refs: Iterable[str] = (),
    accepted_institution_refs: Iterable[str] = (),
) -> LegalSystemReviewProjection:
    superseded = {ref for row in attestations for ref in row.supersedes_attestation_refs}
    credentials = set(accepted_credential_refs)
    institutions = set(accepted_institution_refs)
    active = []
    for row in attestations:
        if row.attestation_ref in superseded:
            continue
        if row.revision_ref != revision_ref or row.build_ref != build_ref:
            continue
        if credentials and not credentials.intersection(row.credential_refs):
            continue
        if institutions and row.institution_ref not in institutions:
            continue
        active.append(row)

    per_claim: dict[str, set[str]] = {}
    for row in active:
        for claim_ref, state in row.claim_states.items():
            per_claim.setdefault(claim_ref, set()).add(state)

    supported: set[str] = set()
    qualified: set[str] = set()
    unsupported: set[str] = set()
    contested: set[str] = set()
    unresolved: set[str] = set()
    for claim_ref, states in per_claim.items():
        positive = bool(states.intersection({"supported", "supported_with_residuals"}))
        negative = "unsupported" in states
        if "contested" in states or (positive and negative):
            contested.add(claim_ref)
        elif negative:
            unsupported.add(claim_ref)
        elif "supported" in states:
            supported.add(claim_ref)
        elif "supported_with_residuals" in states:
            qualified.add(claim_ref)
        else:
            unresolved.add(claim_ref)

    if contested:
        state = "contested_in_scope"
    elif unsupported and not supported and not qualified:
        state = "unsupported_in_scope"
    elif unresolved:
        state = "reviewed_with_open_claims"
    elif qualified:
        state = "supported_with_residuals_in_scope"
    elif supported:
        state = "supported_in_scope"
    else:
        state = "unreviewed_in_scope"

    return LegalSystemReviewProjection(
        revision_ref=revision_ref,
        build_ref=build_ref,
        scope_ref=scope_ref,
        active_attestation_refs=tuple(sorted(row.attestation_ref for row in active)),
        supported_claim_refs=tuple(sorted(supported)),
        qualified_claim_refs=tuple(sorted(qualified)),
        unsupported_claim_refs=tuple(sorted(unsupported)),
        contested_claim_refs=tuple(sorted(contested)),
        unresolved_claim_refs=tuple(sorted(unresolved)),
        reviewer_refs=tuple(sorted({row.reviewer_ref for row in active})),
        institution_refs=tuple(sorted({row.institution_ref for row in active if row.institution_ref})),
        state=state,
    )


__all__ = [
    "LEGAL_SYSTEM_REVIEW_CONTRACT",
    "LegalReviewClaim",
    "LegalSystemReviewAttestation",
    "LegalSystemReviewProjection",
    "create_review_claim",
    "create_system_review_attestation",
    "project_system_review",
]
