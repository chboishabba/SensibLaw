from src.pnf.erdfa_export import erdfa_manifest_overlay
from src.pnf.legal_semantic_export import export_legal_semantic_build


def test_erdfa_overlay_remains_publication_metadata() -> None:
    build = {"build": {"build_ref": "legal-semantic-build:abc"}}
    export = export_legal_semantic_build(build, locators=("ipfs://bafy-test",))
    overlay = erdfa_manifest_overlay(export)

    assert overlay["artifactId"] == "legal-semantic-build:abc"
    assert overlay["containerObjectRef"]["contentDigest"].startswith("sha256:")
    assert overlay["authority"] == "publication_metadata_only"
    assert overlay["semanticPromotionAllowed"] is False
