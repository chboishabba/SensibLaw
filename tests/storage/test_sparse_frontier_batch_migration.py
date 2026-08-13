from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/068_complete_frontier_reduction_and_batch_indexes.sql"
)


def test_document_frontier_reduction_covers_every_non_leaf_kind() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "region.region_kind <> 1" in source
    assert "region.region_kind <> 9" in source
    assert "ORDER BY region.region_kind" in source
    assert "rebuild_numeric_pnf_parent_frontier" in source
    assert "region.region_kind IN (3, 5, 6, 7, 8, 10)" not in source


def test_object_kind_indexing_is_statement_level() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for required in (
        "DROP TRIGGER IF EXISTS semantic_pnf_object_export_kind_index",
        "index_numeric_pnf_object_exports_batch",
        "semantic_pnf_object_export_kind_index_batch",
        "REFERENCING NEW TABLE AS inserted_export",
        "FOR EACH STATEMENT",
        "ON CONFLICT DO NOTHING",
    ):
        assert required in source
    assert "FOR EACH ROW" not in source


def test_batch_index_migration_remains_numeric() -> None:
    source = MIGRATION.read_text(encoding="utf-8").casefold()
    assert " json " not in source
    assert "jsonb" not in source
    assert "::json" not in source
