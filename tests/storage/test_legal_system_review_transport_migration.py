from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "postgres_migrations" / "016_legal_system_review_transport.sql"


def test_system_review_and_transport_migration_contract() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "legal_ir.review_claim" in sql
    assert "legal_ir.system_review_attestation" in sql
    assert "legal_ir.system_review_claim_state" in sql
    assert "legal_ir.system_review_projection" in sql
    assert "transport.legal_artifact_envelope" in sql
    assert "transport.legal_artifact_verification_receipt" in sql
    assert "CHECK (changes_pnf = FALSE)" in sql
    assert "CHECK (trust_imported = FALSE)" in sql
    assert "CHECK (review_state_imported = FALSE)" in sql
    assert "CHECK (truth_closed = FALSE)" in sql
