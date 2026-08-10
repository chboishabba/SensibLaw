from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/076_factor_participation_actor_profiles.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_factor_participation_enriches_actor_profiles_set_wise() -> None:
    source = _source()
    for required in (
        "capture_numeric_pnf_factor_actor_profiles",
        "semantic_pnf_factor_actor_profile",
        "REFERENCING NEW TABLE AS inserted_edge",
        "capture_numeric_pnf_export_factor_profiles",
        "semantic_pnf_export_factor_actor_profile",
        "REFERENCING NEW TABLE AS inserted_export",
        "FOR EACH STATEMENT",
        "edge.role_symbol_id",
        "factor.factor_type_symbol_id",
        "factor.predicate_symbol_id",
        "ON CONFLICT",
    ):
        assert required in source


def test_factor_profile_enrichment_is_persistence_order_independent() -> None:
    source = _source()
    hyperedge_path = source.split(
        "CREATE OR REPLACE FUNCTION execution.capture_numeric_pnf_factor_actor_profiles",
        1,
    )[1].split(
        "CREATE OR REPLACE FUNCTION execution.capture_numeric_pnf_export_factor_profiles",
        1,
    )[0]
    export_path = source.split(
        "CREATE OR REPLACE FUNCTION execution.capture_numeric_pnf_export_factor_profiles",
        1,
    )[1].split("-- Backfill upgraded databases set-wise.", 1)[0]
    assert "inserted_edge AS edge" in hyperedge_path
    assert "semantic_pnf_interface AS interface" in hyperedge_path
    assert "inserted_export AS export" in export_path
    assert "semantic_pnf_hyperedge AS edge" in export_path
    assert "export.interface_id" in export_path


def test_factor_profile_backfill_is_relational_not_generic_only() -> None:
    source = _source()
    backfill = source.split("-- Backfill upgraded databases set-wise.", 1)[1]
    assert "semantic_pnf_hyperedge AS edge" in backfill
    assert "semantic_pnf_factor AS factor" in backfill
    assert "edge.role_symbol_id" in backfill
    assert "factor.factor_type_symbol_id" in backfill
    assert "factor.predicate_symbol_id" in backfill


def test_factor_profile_enrichment_has_no_row_trigger_or_json_authority() -> None:
    source = _source()
    assert "FOR EACH ROW" not in source
    folded = source.casefold()
    assert "jsonb" not in folded
    assert "::json" not in folded
