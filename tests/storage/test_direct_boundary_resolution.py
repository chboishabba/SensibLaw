from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "214_direct_boundary_structural_owner.sql"
)


def test_direct_boundary_completion_uses_structural_start_owner() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "JOIN execution.semantic_parser_partition AS source" in source
    assert "region.start_char >= source.owner_start_char" in source
    assert "region.start_char < source.owner_end_char" in source
    assert "region.end_char <= repair.owner_end_char" not in source
