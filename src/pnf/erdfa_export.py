"""Publication metadata overlays for eRDFa/Kant/federated replay sinks.

These rows describe where immutable SensibLaw bytes were published.  They are not
Legal IR relations and cannot create or promote PNF factors.  Multiple replay
locators may point at the same content-addressed object; mirror count or remote
availability does not create semantic authority.
"""

from __future__ import annotations

from typing import Any

from src.pnf.legal_semantic_export import (
    LEGAL_SEMANTIC_EXPORT_CONTRACT,
    LegalSemanticArtifactExport,
)


def erdfa_manifest_overlay(export: LegalSemanticArtifactExport) -> dict[str, Any]:
    locators = tuple(export.sync_identity.producer_locator_set)
    digest = export.sync_identity.content_digest
    refs = [
        {
            "sink": "content-addressed-replay",
            "uri": locator,
            "contentDigest": digest,
            "semanticAuthority": False,
        }
        for locator in locators
    ]
    return {
        "contractVersion": LEGAL_SEMANTIC_EXPORT_CONTRACT,
        "artifactId": export.semantic_build_ref,
        "artifactRevision": export.export_ref,
        # Backward-compatible first replay locator.  Consumers that understand
        # federation use containerObjectRefs below.
        "containerObjectRef": {
            "sink": "multi-locator",
            "uri": locators[0],
            "contentDigest": digest,
        },
        "containerObjectRefs": refs,
        "memberArtifactRefs": list(export.member_artifact_refs),
        "sourceRevisionRefs": list(export.source_revision_refs),
        "federation": {
            "contentAddressedReplay": True,
            "mirrorCount": len(refs),
            "mirrorSetCreatesSemanticAuthority": False,
            "remoteAvailabilityCreatesClaimTruth": False,
            "remoteAvailabilityCreatesEvidencePayment": False,
        },
        "authority": "publication_metadata_only",
        "semanticPromotionAllowed": False,
    }


__all__ = ["erdfa_manifest_overlay"]
