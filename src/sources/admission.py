"""Deterministic source admission before canonical parsing.

Admission is a generic catalogue concern: it records what an operator supplied
and whether that revision may enter compilation. It never interprets content or
turns a repository/aggregator into a legal authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from src.ontology.external_enrichment import canonical_sha256

SOURCE_ADMISSION_CONTRACT = "source-admission:v0_2"
_ADMISSION_STATES = {"compile", "evidence_only", "exclude"}


@dataclass(frozen=True)
class SourceAdmissionProfile:
    """Versioned role policy applied before parser admission."""

    profile_ref: str
    admitted_roles: tuple[str, ...]
    excluded_roles: Mapping[str, str]
    evidence_only_roles: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceAdmissionReceipt:
    """Immutable classification of one persisted source revision."""

    receipt_ref: str
    source_revision_ref: str
    source_role: str
    semantic_scope: str
    admission_state: str
    exclusion_reason: str | None
    profile_ref: str

    def __post_init__(self) -> None:
        if self.admission_state not in _ADMISSION_STATES:
            raise ValueError("unsupported source admission state")

    @property
    def compile_eligible(self) -> bool:
        return self.admission_state == "compile"

    @property
    def evidence_only(self) -> bool:
        return self.admission_state == "evidence_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "compile_eligible": self.compile_eligible,
            "evidence_only": self.evidence_only,
            "contract_ref": SOURCE_ADMISSION_CONTRACT,
            "authority": "catalogue_admission_only",
            "semantic_state_promoted": False,
            "legal_truth_closed": False,
            "immutable": True,
        }


def admit_source(
    source: Mapping[str, Any], *, profile: SourceAdmissionProfile
) -> SourceAdmissionReceipt:
    """Create an immutable receipt; unknown roles fail closed."""

    role = str(source.get("source_role") or "unclassified")
    revision = str(
        source.get("source_revision_ref") or source.get("document_ref") or ""
    )
    if not revision:
        raise ValueError("source admission requires a source revision reference")

    if role in set(profile.admitted_roles):
        state = "compile"
        reason = None
    elif role in profile.evidence_only_roles:
        state = "evidence_only"
        reason = str(profile.evidence_only_roles[role])
    else:
        state = "exclude"
        reason = str(profile.excluded_roles.get(role) or "role_not_compile_eligible")

    identity = {
        "contract": SOURCE_ADMISSION_CONTRACT,
        "profile": profile.profile_ref,
        "revision": revision,
        "role": role,
        "semantic_scope": str(source.get("semantic_scope") or "source_material"),
        "state": state,
        "reason": reason,
    }
    return SourceAdmissionReceipt(
        receipt_ref="source-admission:" + canonical_sha256(identity),
        source_revision_ref=revision,
        source_role=role,
        semantic_scope=str(source.get("semantic_scope") or "source_material"),
        admission_state=state,
        exclusion_reason=reason,
        profile_ref=profile.profile_ref,
    )


def classify_catalogue(
    sources: Iterable[Mapping[str, Any]], *, profile: SourceAdmissionProfile
) -> tuple[SourceAdmissionReceipt, ...]:
    return tuple(
        sorted(
            (admit_source(row, profile=profile) for row in sources),
            key=lambda row: (row.source_revision_ref, row.receipt_ref),
        )
    )


def admission_manifest(
    receipts: Iterable[SourceAdmissionReceipt],
) -> dict[str, Any]:
    """Return a deterministic build-facing admission summary."""

    ordered = tuple(sorted(receipts, key=lambda row: row.receipt_ref))
    counts = {state: 0 for state in sorted(_ADMISSION_STATES)}
    for receipt in ordered:
        counts[receipt.admission_state] += 1
    return {
        "contract_ref": SOURCE_ADMISSION_CONTRACT,
        "receipt_refs": [row.receipt_ref for row in ordered],
        "counts": counts,
        "receipts": [row.to_dict() for row in ordered],
        "parser_admitted_revision_refs": [
            row.source_revision_ref for row in ordered if row.compile_eligible
        ],
        "network_activity_permitted": False,
    }


OFFLINE_HCA_REGRESSION_PROFILE = SourceAdmissionProfile(
    profile_ref="profile:offline-hca-regression:v0_2",
    admitted_roles=(
        "hearing_transcript",
        "judgment",
        "submissions",
        "chronology",
        "appeal_document",
        "reply_document",
        "outline_document",
        "transcript_media",
    ),
    evidence_only_roles={
        "navigation": "navigation_discovery_evidence_only",
        "search": "search_discovery_evidence_only",
        "database_page": "database_discovery_evidence_only",
        "landing_page": "landing_discovery_evidence_only",
        "oembed": "oembed_transport_evidence_only",
        "recording_page": "recording_transport_evidence_only",
    },
    excluded_roles={
        "duplicate_caption": "derived_duplicate_caption",
        "support_material": "unrelated_support_material",
    },
)

AU_PRIMARY_LEGAL_SOURCE_PROFILE = SourceAdmissionProfile(
    profile_ref="profile:au-primary-legal-source:v0_1",
    admitted_roles=(
        "primary_legislation",
        "delegated_legislation",
        "judgment",
    ),
    evidence_only_roles={
        "repository_record": "repository_transport_evidence_only",
        "aggregator_record": "aggregator_transport_evidence_only",
        "navigation": "navigation_discovery_evidence_only",
        "search": "search_discovery_evidence_only",
        "landing_page": "landing_discovery_evidence_only",
    },
    excluded_roles={
        "commentary": "commentary_not_primary_authority",
        "duplicate_caption": "derived_duplicate_caption",
        "support_material": "unrelated_support_material",
    },
)


__all__ = [
    "AU_PRIMARY_LEGAL_SOURCE_PROFILE",
    "OFFLINE_HCA_REGRESSION_PROFILE",
    "SOURCE_ADMISSION_CONTRACT",
    "SourceAdmissionProfile",
    "SourceAdmissionReceipt",
    "admission_manifest",
    "admit_source",
    "classify_catalogue",
]
