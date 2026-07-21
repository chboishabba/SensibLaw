"""Publication metadata overlays for eRDFa/Kant sinks.

These rows describe where immutable SensibLaw bytes were published.  They are not
Legal IR relations and cannot create or promote PNF factors.
"""

from __future__ import annotations

from typing import Any

from src.pnf.legal_semantic_export import (
    LEGAL_SEMANTIC_EXPORT_CONTRACT,
    LegalSemanticArtifactExport,
)


def erdfa_manifest_overlay(export: LegalSemanticArtifactExport) -> dict[str, Any]:
    return {
        "contractVersion": LEGAL_SEMANTIC_EXPORT_CONTRACT,
        "artifactId": export.semantic_build_ref,
        "artifactRevision": export.export_ref,
        "containerObjectRef": {
            "sink": "multi-locator",
            "uri": export.sync_identity.producer_locator_set[0],
            "contentDigest": export.sync_identity.content_digest,
        },
        "memberArtifactRefs": list(export.member_artifact_refs),
        "sourceRevisionRefs": list(export.source_revision_refs),
        "authority": "publication_metadata_only",
        "semanticPromotionAllowed": False,
    }


__all__ = ["erdfa_manifest_overlay"]
