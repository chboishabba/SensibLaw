from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
M204 = ROOT / "database/postgres_migrations/204_parent_output_delta_fingerprints.sql"
M205 = ROOT / "database/postgres_migrations/205_deterministic_parent_output_fingerprints.sql"
M206 = ROOT / "database/postgres_migrations/206_affected_key_parent_local_reduction.sql"


def test_emitted_delta_count_is_output_change_not_input_touch_count() -> None:
    sql = M204.read_text()
    assert "semantic_pnf_parent_output_fingerprint" in sql
    assert "refresh_numeric_pnf_parent_output_fingerprints" in sql
    assert "current_digest IS DISTINCT FROM compared.prior_digest" in sql
    assert "emitted_value := execution.refresh_numeric_pnf_parent_output_fingerprints" in sql
    assert "emitted_value := CASE WHEN cold_value THEN output_value ELSE touched END" not in sql


def test_actor_output_fingerprint_is_deterministic_with_multiple_predicates() -> None:
    sql = M205.read_text()
    assert "string_agg(" in sql
    assert "ORDER BY" in sql
    assert "COALESCE(profile.predicate_symbol_id, 0)" in sql
    assert "ON CONFLICT (interface_id, key_family, key_a, key_b, key_c)" not in sql


def test_accumulated_exact_key_families_are_bounded_not_only_touched_work() -> None:
    sql = M204.read_text()
    assert "accumulated_object_keys" in sql
    assert "accumulated_factor_keys" in sql
    assert "accumulated_demand_keys" in sql
    assert "exceeds accumulated exact key budget" in sql


def test_warm_path_dependency_closes_affected_keys() -> None:
    sql = M206.read_text()
    expand = sql[
        sql.index("CREATE OR REPLACE FUNCTION execution.expand_numeric_pnf_parent_affected_keys") :
        sql.index("CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_affected")
    ]
    assert "key.key_family = 4" in expand  # actor -> object
    assert "semantic_pnf_hyperedge" in expand  # factor -> actor participants
    assert "demand.expected_target_kind = 1" in expand
    assert "demand.expected_target_kind = 2" in expand


def test_warm_reducer_never_reopens_child_interface_export_chain() -> None:
    sql = M206.read_text()
    reducer = sql[
        sql.index("CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_affected") :
        sql.index("-- Activate key-local warm reduction")
    ]
    assert "semantic_pnf_parent_delta_projection" in reducer
    assert "semantic_pnf_parent_actor_delta_projection" in reducer
    assert "JOIN execution.semantic_pnf_interface AS child_interface" not in reducer
    assert "child_region.parent_region_id" not in reducer


def test_warm_export_mutation_is_relational_delta_not_interface_rebuild() -> None:
    sql = M206.read_text()
    reducer = sql[
        sql.index("CREATE OR REPLACE FUNCTION execution.reduce_numeric_pnf_parent_frontier_affected") :
        sql.index("-- Activate key-local warm reduction")
    ]
    assert "pg_temp.numeric_pnf_desired_parent_export" in reducer
    assert "ROW(" in reducer and "IS DISTINCT FROM ROW(" in reducer
    assert "WHERE current.interface_id = selected_interface_id" in reducer
    assert "DELETE FROM execution.semantic_pnf_interface_export\n     WHERE interface_id = selected_interface_id;" not in reducer


def test_lookup_rebuild_is_restricted_to_dirty_admitted_targets() -> None:
    sql = M206.read_text()
    lookup = sql[
        sql.index("-- Lookup is a projection of changed admitted exports only") :
        sql.index("-- Bounded parent publication summary")
    ]
    assert "pg_temp.numeric_pnf_dirty_target" in lookup
    assert "FROM execution.semantic_pnf_interface_export AS export" in lookup
    assert "semantic_pnf_interface_lookup AS child_lookup" not in lookup
    assert "semantic_pnf_parent_delta_projection" not in lookup


def test_cold_and_warm_paths_are_distinct() -> None:
    sql = M206.read_text()
    wrapper = sql[sql.index("-- Activate key-local warm reduction") :]
    assert "IF cold_value THEN" in wrapper
    assert "rebuild_numeric_pnf_parent_frontier_delta_input" in wrapper
    assert "reduce_numeric_pnf_parent_frontier_affected" in wrapper
    assert "IF NOT cold_value AND touched = 0 THEN" in wrapper
