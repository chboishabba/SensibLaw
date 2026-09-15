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


def test_erdfa_overlay_retains_all_federated_replay_locators_without_importing_authority() -> None:
    build = {"build": {"build_ref": "legal-semantic-build:mabo"}}
    export = export_legal_semantic_build(
        build,
        locators=(
            "ipfs://bafy-mabo",
            "https://mirror-a.example/mabo",
            "https://mirror-b.example/mabo",
        ),
    )
    overlay = erdfa_manifest_overlay(export)

    refs = overlay["containerObjectRefs"]
    assert [row["uri"] for row in refs] == [
        "https://mirror-a.example/mabo",
        "https://mirror-b.example/mabo",
        "ipfs://bafy-mabo",
    ]
    assert len({row["contentDigest"] for row in refs}) == 1
    assert overlay["federation"]["contentAddressedReplay"] is True
    assert overlay["federation"]["mirrorSetCreatesSemanticAuthority"] is False
    assert overlay["federation"]["remoteAvailabilityCreatesClaimTruth"] is False
    assert overlay["semanticPromotionAllowed"] is False
