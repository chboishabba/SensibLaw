from __future__ import annotations

from src.pnf.legal_artifact_transport import (
    LegalArtifactMember,
    export_legal_artifact,
    verify_imported_artifact,
)


def test_export_matches_zos_identity_and_import_does_not_promote() -> None:
    member = LegalArtifactMember(
        member_ref="legal-ir-projection:1",
        member_kind="artifact",
        content_digest="sha256:" + "1" * 64,
        producer_contract="sensiblaw/legal-ir-projection/v1",
    )
    envelope, payload = export_legal_artifact(
        object_id="legal-semantic-build:1",
        payload={"build_ref": "legal-semantic-build:1", "state": "candidate"},
        producer_contract="sensiblaw/legal-semantic-build/v1",
        locators=("ipfs://cid", "https://example.test/build/1"),
        semantic_build_ref="legal-semantic-build:1",
        source_revision_refs=("source-revision:1",),
        members=(member,),
    )

    assert envelope.sync_identity[0] == "artifact"
    assert envelope.sync_identity[1] == "legal-semantic-build:1"
    assert envelope.to_dict()["semanticPromotionPerformed"] is False
    assert envelope.to_dict()["trustImported"] is False

    receipt = verify_imported_artifact(
        envelope=envelope,
        payload_bytes=payload,
        locator_ref="ipfs://cid",
        available_member_refs=("legal-ir-projection:1",),
    )

    assert receipt.verification_state == "verified_available"
    assert receipt.member_states["legal-ir-projection:1"] == "available"
    assert receipt.to_dict()["semantic_promotion_performed"] is False
    assert receipt.to_dict()["review_state_imported"] is False


def test_digest_mismatch_is_not_admitted_as_verified() -> None:
    envelope, _payload = export_legal_artifact(
        object_id="federation-bundle:1",
        payload={"bundle_ref": "federation-bundle:1"},
        producer_contract="sensiblaw/federation-bundle/v1",
    )
    receipt = verify_imported_artifact(
        envelope=envelope,
        payload_bytes=b"different",
        locator_ref="https://peer.test/bundle/1",
    )

    assert receipt.verification_state == "digest_mismatch"
    assert receipt.expected_digest != receipt.observed_digest
