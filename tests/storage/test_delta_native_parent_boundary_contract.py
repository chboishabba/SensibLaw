from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
M202 = ROOT / "database/postgres_migrations/202_delta_native_parent_boundary.sql"
M203 = ROOT / "database/postgres_migrations/203_activate_delta_native_parent_reducer.sql"
PY = ROOT / "src/storage/postgres/numeric_parent_delta_reducer.py"


def test_transport_carrier_is_semantically_complete() -> None:
    sql = M202.read_text()
    assert "ADD COLUMN IF NOT EXISTS scope_class" in sql
    assert "ADD COLUMN IF NOT EXISTS origin_interface_id" in sql
    assert "ADD COLUMN IF NOT EXISTS outward_required" in sql
    assert "semantic_pnf_parent_actor_delta_projection" in sql
    assert "transport_numeric_pnf_actor_delta_insert" in sql
    assert "transport_numeric_pnf_actor_delta_delete" in sql
    assert "transport_numeric_pnf_actor_delta_update" in sql


def test_affected_keys_are_durable_across_insert_update_delete() -> None:
    sql = M202.read_text()
    assert "semantic_pnf_parent_affected_key" in sql
    assert "mark_numeric_pnf_export_keys_insert" in sql
    assert "mark_numeric_pnf_export_keys_update" in sql
    assert "mark_numeric_pnf_export_keys_delete" in sql
    assert "mark_numeric_pnf_actor_keys_insert" in sql
    assert "mark_numeric_pnf_actor_keys_update" in sql
    assert "mark_numeric_pnf_actor_keys_delete" in sql
    assert "REFERENCING OLD TABLE AS deleted_projection" in sql
    assert "REFERENCING OLD TABLE AS deleted_actor" in sql


def test_delta_input_reducer_does_not_reopen_child_export_join_chain() -> None:
    sql = M202.read_text()
    start = sql.index(
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_delta_input"
    )
    end = sql.index(
        "CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_delta_native",
        start,
    )
    reducer = sql[start:end]
    assert "semantic_pnf_parent_delta_projection" in reducer
    assert "semantic_pnf_parent_actor_delta_projection" in reducer
    assert "JOIN execution.semantic_pnf_interface AS child_interface" not in reducer
    assert "child_region.parent_region_id = selected_region_id" not in reducer


def test_lookup_is_derived_from_admitted_parent_export() -> None:
    sql = M202.read_text()
    start = sql.index("-- Lookup is derived from admitted parent exports")
    end = sql.index("-- Demand solving is unchanged semantically", start)
    lookup = sql[start:end]
    assert "FROM execution.semantic_pnf_interface_export AS export" in lookup
    assert "semantic_pnf_interface_lookup AS child_lookup" not in lookup
    assert "semantic_pnf_parent_delta_projection" not in lookup


def test_canonical_api_routes_through_delta_native_bridge() -> None:
    sql = M203.read_text()
    assert "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier" in sql
    assert "execution.reduce_numeric_pnf_parent_frontier_delta_native" in sql
    assert "execution.rebuild_numeric_pnf_parent_frontier_delta_input" not in sql


def test_python_bridge_separates_structural_work_from_wall_acceptance() -> None:
    source = PY.read_text()
    assert "affected_keys_from_fingerprints" in source
    assert "accumulated_boundary_keys" in source
    assert "touched_boundary_keys" in source
    assert "hierarchy_transport_work" in source
    assert "parser_wall" not in source
    assert "post_parser_wall" not in source
    assert "acceptance_eligible" not in source
