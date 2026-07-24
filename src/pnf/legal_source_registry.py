"""Durable registry coordinates for already-persisted legal sources.

These rows prove acquisition/admission provenance and retrieval compatibility.
They never close applicability or legal truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.policy.carriers.canonical import canonical_sha256


@dataclass(frozen=True)
class RegisteredLegalSource:
    source_revision_ref: str
    document_ref: str
    admission_receipt_ref: str
    jurisdiction_ref: str
    source_role: str
    authority_level: str
    canonical_text_sha256: str
    media_type: str = "text/plain"
    acquisition_receipt_ref: str | None = None
    temporal_refs: tuple[str, ...] = ()
    provider_profile_refs: tuple[str, ...] = ()
    compile_eligible: bool = True

    @property
    def registry_ref(self) -> str:
        return "legal-source-registry:" + canonical_sha256(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_ref": self.registry_ref,
            **asdict(self),
            "authority": "persisted_source_revision_only",
            "identity_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }

    def planning_row(self) -> dict[str, Any]:
        """Return the narrower carrier accepted by plan_legal_sources."""

        return {
            "source_revision_ref": self.source_revision_ref,
            "jurisdiction_ref": self.jurisdiction_ref,
            "source_role": self.source_role,
            "authority_level": self.authority_level,
            "temporal_refs": self.temporal_refs,
            "provider_profile_refs": self.provider_profile_refs,
            "compile_eligible": self.compile_eligible,
        }


__all__ = ["RegisteredLegalSource"]
