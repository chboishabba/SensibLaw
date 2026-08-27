from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/200_fix_affected_frontier_ordering.sql"


def test_affected_frontier_select_projects_its_ordering_expression() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "SELECT DISTINCT candidate.interface_id" in sql
    assert "candidate.end_char - candidate.start_char AS span_length" in sql
    assert "ORDER BY candidate.region_kind" in sql
    assert "span_length" in sql


def test_ordering_patch_preserves_canonical_carrier_boundary() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "region.region_kind NOT IN (1, 2, 4, 9)" in sql
    assert "child_region.region_kind NOT IN (2, 4, 9)" in sql
    assert "execution.rebuild_numeric_pnf_parent_frontier" in sql
    assert "semantic_pnf_interface_export" not in sql
    assert "semantic_pnf_interface_lookup" not in sql
