from src.pnf.legal_semantic_export import export_legal_semantic_build, verify_legal_semantic_import


def test_sync_identity_verifies_without_promoting_semantics() -> None:
    build = {
        "build": {"build_ref": "legal-semantic-build:abc"},
        "legal_ir_projection": {"projection_ref": "legal-ir-projection:1"},
    }
    export = export_legal_semantic_build(build, locators=("ipfs://bafy-test",))
    row = export.to_dict()

    assert row["sync_identity"]["kind"] == "artifact"
    assert row["sync_identity"]["object_id"] == "legal-semantic-build:abc"
    assert row["sync_identity"]["semantic_authority"] is False
    assert row["import_effects"]["pnf_promoted"] is False
    assert row["import_effects"]["legal_truth_closed"] is False

    receipt = verify_legal_semantic_import(build, row)
    assert receipt["state"] == "verified_available"
    assert receipt["promotion_performed"] is False
    assert receipt["trust_imported"] is False
