from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
M179 = ROOT / "database/postgres_migrations/179_indexed_sparse_frontier_actor_retention.sql"
M076 = ROOT / "database/postgres_migrations/076_delta_fed_canonical_parent_reducer.sql"


def test_179_recognizes_delta_fed_c3_actor_retention_owner() -> None:
    migration = M179.read_text(encoding="utf-8")
    c3 = M076.read_text(encoding="utf-8")

    assert "semantic_pnf_parent_delta_projection AS demand_export" in c3
    assert "semantic_pnf_parent_delta_projection AS demand_export" in migration
    assert "demand_export.parent_region_id = selected_region_id" in migration
    assert "demand_export.target_kind = 3" in migration
    assert "historical_boundary OR delta_boundary" in migration


def test_179_keeps_fail_closed_semantic_predicate_checks() -> None:
    migration = M179.read_text(encoding="utf-8")

    for required in (
        "demand.expected_target_kind = 1",
        "demand.expected_object_kind_symbol_id IS NULL",
        "demand.role_symbol_id IS NULL",
        "demand.expected_factor_type_symbol_id IS NULL",
        "migration 179 refuses to replace an unrecognised actor-retention implementation",
    ):
        assert required in migration


def test_179_recognizes_both_historical_and_c3_stage_boundaries() -> None:
    migration = M179.read_text(encoding="utf-8")

    assert "Unresolved holes always cross the boundary" in migration
    assert "Unresolved holes cross the boundary from the transported delta carrier" in migration
