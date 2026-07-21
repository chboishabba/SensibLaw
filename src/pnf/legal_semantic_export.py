"""Transport/provenance export for immutable Legal Semantic Builds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from src.ontology.external_enrichment import canonical_sha256
from src.pnf.sync_identity import CanonicalSyncIdentity


LEGAL_SEMANTIC_EXPORT_CONTRACT = "sensiblaw/legal-semantic-build/v1"


@dataclass(frozen=True)
class LegalSemanticArtifactExport:
    sync_identity: CanonicalSyncIdentity
    semantic_build_ref: str
    source_revision_refs: tuple[str, ...]
    member_artifact_refs: tuple[str, ...]
    payload_sha256: str
    publication_metadata: Mapping[str, Any]

    @property
    def export_ref(self) -> str:
        return "legal-semantic-export:" + canonical_sha256(
            {
                "identity": self.sync_identity.to_dict(),
                "semantic_build_ref": self.semantic_build_ref,
                "source_revision_refs": self.source_revision_refs,
                "member_artifact_refs": self.member_artifact_refs,
                "payload_sha256": self.payload_sha256,
                "publication_metadata": dict(self.publication_metadata),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": LEGAL_SEMANTIC_EXPORT_CONTRACT,
            "export_ref": self.export_ref,
            "sync_identity": self.sync_identity.to_dict(),
            "semantic_build_ref": self.semantic_build_ref,
            "source_revision_refs": list(self.source_revision_refs),
            "member_artifact_refs": list(self.member_artifact_refs),
            "payload_sha256": self.payload_sha256,
            "publication_metadata": dict(self.publication_metadata),
            "import_effects": {
                "artifact_available": True,
                "review_started": False,
                "pnf_promoted": False,
                "legal_ir_promoted": False,
                "identity_closed": False,
                "trust_imported": False,
                "legal_truth_closed": False,
            },
            "authority": "transport_and_provenance_only",
        }


def export_legal_semantic_build(
    build: Mapping[str, Any],
    *,
    locators: Sequence[str],
    member_artifact_refs: Sequence[str] = (),
    source_revision_refs: Sequence[str] = (),
    publication_metadata: Mapping[str, Any] | None = None,
) -> LegalSemanticArtifactExport:
    build_row = build.get("build") if isinstance(build.get("build"), Mapping) else build
    semantic_build_ref = str(build_row.get("build_ref") or "")
    if not semantic_build_ref:
        raise ValueError("Legal Semantic Build requires build_ref")
    locator_rows = tuple(sorted(set(str(value) for value in locators if value)))
    if not locator_rows:
        raise ValueError("at least one replay locator is required")
    payload_sha256 = canonical_sha256(build)
    identity = CanonicalSyncIdentity(
        kind="artifact",
        object_id=semantic_build_ref,
        content_digest=f"sha256:{payload_sha256}",
        producer_contract=LEGAL_SEMANTIC_EXPORT_CONTRACT,
        producer_locator_set=locator_rows,
    )
    return LegalSemanticArtifactExport(
        sync_identity=identity,
        semantic_build_ref=semantic_build_ref,
        source_revision_refs=tuple(sorted(set(str(value) for value in source_revision_refs if value))),
        member_artifact_refs=tuple(sorted(set(str(value) for value in member_artifact_refs if value))),
        payload_sha256=payload_sha256,
        publication_metadata=dict(publication_metadata or {}),
    )


def verify_legal_semantic_import(
    build: Mapping[str, Any], export_row: Mapping[str, Any]
) -> dict[str, Any]:
    expected_digest = canonical_sha256(build)
    identity = export_row.get("sync_identity") or {}
    build_row = build.get("build") if isinstance(build.get("build"), Mapping) else build
    build_ref = str(build_row.get("build_ref") or "")
    errors: list[str] = []
    if str(export_row.get("contract_version") or "") != LEGAL_SEMANTIC_EXPORT_CONTRACT:
        errors.append("unsupported_contract")
    if str(export_row.get("semantic_build_ref") or "") != build_ref:
        errors.append("object_id_mismatch")
    if str(export_row.get("payload_sha256") or "") != expected_digest:
        errors.append("payload_digest_mismatch")
    if str(identity.get("content_digest") or "") != f"sha256:{expected_digest}":
        errors.append("sync_digest_mismatch")
    if str(identity.get("object_id") or "") != build_ref:
        errors.append("sync_object_id_mismatch")
    return {
        "state": "verified_available" if not errors else "rejected",
        "errors": errors,
        "semantic_build_ref": build_ref,
        "payload_sha256": expected_digest,
        "promotion_performed": False,
        "review_started": False,
        "identity_closed": False,
        "trust_imported": False,
        "legal_truth_closed": False,
        "authority": "verification_receipt_only",
    }


__all__ = [
    "LEGAL_SEMANTIC_EXPORT_CONTRACT",
    "LegalSemanticArtifactExport",
    "export_legal_semantic_build",
    "verify_legal_semantic_import",
]
