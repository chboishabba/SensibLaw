"""Deterministic source admission before canonical parsing.

Admission is a generic catalogue concern: it records what an operator supplied
and whether that revision may enter compilation.  It never interprets content
or turns a repository/aggregator into a legal authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from src.ontology.external_enrichment import canonical_sha256

SOURCE_ADMISSION_CONTRACT = "source-admission:v0_1"


@dataclass(frozen=True)
class SourceAdmissionProfile:
    profile_ref: str
    admitted_roles: tuple[str, ...]
    excluded_roles: Mapping[str, str]


@dataclass(frozen=True)
class SourceAdmissionReceipt:
    receipt_ref: str
    source_revision_ref: str
    source_role: str
    semantic_scope: str
    compile_eligible: bool
    exclusion_reason: str | None
    profile_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "contract_ref": SOURCE_ADMISSION_CONTRACT,
            "authority": "catalogue_admission_only",
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
    eligible = role in set(profile.admitted_roles)
    reason = (
        None
        if eligible
        else str(profile.excluded_roles.get(role) or "role_not_compile_eligible")
    )
    identity = {
        "contract": SOURCE_ADMISSION_CONTRACT,
        "profile": profile.profile_ref,
        "revision": revision,
        "role": role,
        "eligible": eligible,
        "reason": reason,
    }
    return SourceAdmissionReceipt(
        receipt_ref="source-admission:" + canonical_sha256(identity),
        source_revision_ref=revision,
        source_role=role,
        semantic_scope=str(source.get("semantic_scope") or "source_material"),
        compile_eligible=eligible,
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


OFFLINE_HCA_REGRESSION_PROFILE = SourceAdmissionProfile(
    profile_ref="profile:offline-hca-regression:v0_1",
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
    excluded_roles={
        "navigation": "navigation_not_substantive",
        "search": "search_not_substantive",
        "database_page": "database_page_not_substantive",
        "landing_page": "landing_not_substantive",
        "oembed": "oembed_not_substantive",
        "recording_page": "recording_page_not_transcript_media",
        "duplicate_caption": "derived_duplicate_caption",
        "support_material": "unrelated_support_material",
    },
)


__all__ = [
    "OFFLINE_HCA_REGRESSION_PROFILE",
    "SOURCE_ADMISSION_CONTRACT",
    "SourceAdmissionProfile",
    "SourceAdmissionReceipt",
    "admit_source",
    "classify_catalogue",
]
