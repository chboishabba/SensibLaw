from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def test_entity_surface_projection_is_statement_level() -> None:
    sql = (MIGRATIONS / "158_setwise_parser_entity_surface_labels.sql").read_text(
        encoding="utf-8"
    )

    assert "DROP TRIGGER IF EXISTS semantic_parser_entity_surface_label_refresh" in sql
    assert "REFERENCING NEW TABLE AS inserted_entity" in sql
    assert "REFERENCING OLD TABLE AS prior_entity NEW TABLE AS updated_entity" in sql
    assert sql.count("FOR EACH STATEMENT") == 2
    assert "FOR EACH ROW" not in sql
    assert "FOR entity IN" not in sql


def test_surface_symbols_are_interned_as_one_returned_relation() -> None:
    sql = (MIGRATIONS / "158_setwise_parser_entity_surface_labels.sql").read_text(
        encoding="utf-8"
    )

    # The human surface string is an explicit provider/audit boundary. Intern it
    # once per distinct surface and consume RETURNING directly so the statement
    # never relies on seeing its own writes through a sibling base-table scan.
    assert "SELECT DISTINCT 1::SMALLINT" in sql
    assert "ON CONFLICT(kind_id,symbol_text) DO UPDATE SET" in sql
    assert "RETURNING symbol_id,symbol_text" in sql
    assert "JOIN intern ON intern.symbol_text=valid_surface.surface_text" in sql
    assert "ensure_semantic_symbol(1::SMALLINT" not in sql


def test_surface_reconstruction_is_entity_partitioned() -> None:
    sql = (MIGRATIONS / "158_setwise_parser_entity_surface_labels.sql").read_text(
        encoding="utf-8"
    )

    assert "PARTITION BY entity.entity_id" in sql
    assert "PARTITION BY changed.entity_id" in sql
    assert "token.start_char>=entity.start_char" in sql
    assert "token.end_char<=entity.end_char" in sql
    assert "token.start_char>=changed.start_char" in sql
    assert "token.end_char<=changed.end_char" in sql
