from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/065_actor_profile_dimension_integrity.sql"
)


def test_actor_profile_dimension_integrity_uses_generated_fk_projections() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for required in (
        "ALTER COLUMN object_kind_symbol_id SET NOT NULL",
        "ALTER COLUMN role_symbol_id SET NOT NULL",
        "ALTER COLUMN factor_type_symbol_id SET NOT NULL",
        "ALTER COLUMN predicate_symbol_id SET NOT NULL",
        "semantic_pnf_actor_profile_dimension_ck",
        "object_kind_symbol_fk",
        "role_symbol_fk",
        "factor_type_symbol_fk",
        "predicate_symbol_fk",
        "NULLIF(object_kind_symbol_id, 0)",
        "NULLIF(role_symbol_id, 0)",
        "NULLIF(factor_type_symbol_id, 0)",
        "NULLIF(predicate_symbol_id, 0)",
        "REFERENCES execution.semantic_symbol(symbol_id)",
    ):
        assert required in source


def test_actor_profile_integrity_adds_no_row_trigger_queries() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TRIGGER" not in source
    assert "CREATE OR REPLACE FUNCTION" not in source
    assert "WHERE NOT EXISTS" not in source
    assert " json " not in source.casefold()
    assert "jsonb" not in source.casefold()
