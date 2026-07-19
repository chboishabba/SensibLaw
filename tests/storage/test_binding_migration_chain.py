from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def test_binding_migrations_repair_active_document_authority_and_add_reuse() -> None:
    migration_008 = (MIGRATIONS / "008_binding_candidate_sets.sql").read_text(
        encoding="utf-8"
    )
    migration_010 = (
        MIGRATIONS / "010_binding_active_document_fks.sql"
    ).read_text(encoding="utf-8")
    migration_011 = (
        MIGRATIONS / "011_operational_document_build_reuse.sql"
    ).read_text(encoding="utf-8")
    migration_012 = (
        MIGRATIONS / "012_binding_demand_links.sql"
    ).read_text(encoding="utf-8")
    migration_013 = (
        MIGRATIONS / "013_canonical_text_coordinate_build.sql"
    ).read_text(encoding="utf-8")
    migration_014 = (
        MIGRATIONS / "014_external_pnf_enrichment.sql"
    ).read_text(encoding="utf-8")

    assert "REFERENCES compiler_document(document_ref)" in migration_008
    assert "DROP CONSTRAINT IF EXISTS factor_anchor_document_ref_fkey" in (
        migration_010
    )
    assert "DROP CONSTRAINT IF EXISTS binding_candidate_set_document_ref_fkey" in (
        migration_010
    )
    assert migration_010.count("REFERENCES corpus.document(document_ref)") == 2

    assert "execution.document_compilation_build" in migration_011
    assert "execution.document_compilation_build_demand" in migration_011
    assert "build_key_sha256 BYTEA NOT NULL UNIQUE" in migration_011
    assert "UNIQUE (document_ref, compiler_contract_ref, build_key_sha256)" in (
        migration_011
    )

    assert "resolution.demand_candidate_set" in migration_012
    assert "resolution.v_binding_demand" in migration_012
    assert "REFERENCES resolution.demand(demand_ref)" in migration_012
    assert "REFERENCES resolution.binding_candidate_set(candidate_set_ref)" in (
        migration_012
    )

    assert "compiler.document.local-binding" in migration_013
    assert "'v0_8'" in migration_013
    assert "canonical text coordinate system" in migration_013

    assert "CREATE SCHEMA IF NOT EXISTS enrichment" in migration_014
    assert "enrichment.external_candidate_set" in migration_014
    assert "enrichment.pressure_receipt" in migration_014
    assert "CHECK (identity_closed = FALSE)" in migration_014
    assert "REFERENCES resolution.demand(demand_ref)" in migration_014
    assert "candidate_payload JSONB" not in (
        migration_010 + migration_011 + migration_012 + migration_013 + migration_014
    )
