from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "211_deferred_hierarchy_publication_barriers.sql"
)
PLANNER = ROOT / "src" / "storage" / "postgres" / "numeric_hierarchy_planner.py"


def test_211_makes_existing_defer_contract_effective() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "sensiblaw.defer_frontier_rebuild" in sql
    assert "sensiblaw.force_frontier_rebuild" in sql
    assert "IF defer_requested AND NOT force_requested THEN" in sql
    deferred = sql.split("IF defer_requested AND NOT force_requested THEN", 1)[1].split(
        "configured_budget :=", 1
    )[0]
    assert "reduce_numeric_pnf_parent_frontier_delta_native" not in deferred
    assert "RETURN;" in deferred


def test_document_reducer_is_the_forced_publication_barrier() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    barrier = sql.split(
        "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_document_frontiers",
        1,
    )[1]
    assert "set_config('sensiblaw.force_frontier_rebuild', 'on', true)" in barrier
    assert "execution.rebuild_numeric_pnf_parent_frontier" in barrier
    assert "ORDER BY region.region_kind" in barrier
    assert "EXCEPTION WHEN OTHERS" in barrier


def test_python_hierarchy_already_declares_deferred_materialization() -> None:
    source = PLANNER.read_text(encoding="utf-8")
    assert '"sensiblaw.defer_frontier_rebuild", "on"' in source
    assert source.count("reduce_numeric_pnf_document_frontiers") >= 2
    # This is the formerly-expensive per-shell call.  Migration 211 now turns
    # it into a non-publishing read while the enclosing planner has defer=on.
    assert "rebuild_numeric_pnf_parent_frontier" in source


def test_211_preserves_the_delta_native_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "reduce_numeric_pnf_parent_frontier_delta_native" in sql
    assert "semantic_pnf_interface_export" not in sql
    assert "semantic_pnf_interface_lookup" not in sql
    assert "semantic_pnf_demand_candidate" not in sql
