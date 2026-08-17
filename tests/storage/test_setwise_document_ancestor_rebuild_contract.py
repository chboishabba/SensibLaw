from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/142_setwise_document_ancestor_rebuild.sql"


def test_document_ancestor_rebuild_is_setwise_not_interface_looped() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "WITH RECURSIVE chain(" in sql
    assert "generate_series(0, 62)" in sql
    assert "chain.distance = (1::BIGINT << power.distance_power)" in sql
    assert "DISTINCT ON (" in sql
    assert "ancestor_region.region_kind" in sql
    assert "FOR row IN" not in sql
    assert "PERFORM execution.rebuild_pnf_interface_ancestors" not in sql


def test_document_rebuild_preserves_both_ancestor_projections() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "INSERT INTO execution.semantic_pnf_interface_ancestor" in sql
    assert "INSERT INTO execution.semantic_pnf_interface_typed_ancestor" in sql
    assert "ON CONFLICT (interface_id, distance_power) DO UPDATE" in sql
    assert "ON CONFLICT (interface_id, ancestor_region_kind) DO UPDATE" in sql
