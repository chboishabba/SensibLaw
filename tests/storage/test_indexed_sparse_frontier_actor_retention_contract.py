from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database/postgres_migrations/179_indexed_sparse_frontier_actor_retention.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_actor_retention_uses_indexed_kind_role_factor_intersection() -> None:
    source = _source()

    assert (
        "CREATE OR REPLACE FUNCTION execution.indexed_numeric_pnf_demanded_actor_profiles("
        in source
    )
    assert "required_key AS MATERIALIZED" in source
    assert "profile_key AS MATERIALIZED" in source
    assert "matched_profile AS MATERIALIZED" in source
    assert "required.required_count = matched.matched_count" in source
    assert "constraint_row.key_kind IN (1, 2, 4)" in source
    assert "profile.factor_type_symbol_id" in source
    assert "profile.object_kind_symbol_id" in source
    assert "profile.role_symbol_id" in source


def test_actor_retention_deliberately_does_not_add_lexical_matching() -> None:
    source = _source()

    helper = source.split("DO $migration$", 1)[0]
    assert "lexical_symbol_id" not in helper
    assert "profile.predicate_symbol_id" in helper
    assert "profile.head_symbol_id" not in helper


def test_actor_retention_constraint_fibre_is_checked_fail_closed() -> None:
    source = _source()

    assert "expected_key AS" in source
    assert "actual_key AS" in source
    assert "SELECT * FROM expected_key EXCEPT SELECT * FROM actual_key" in source
    assert "SELECT * FROM actual_key EXCEPT SELECT * FROM expected_key" in source
    assert "actor-retention constraint fibre disagrees" in source
    assert "RAISE EXCEPTION" in source


def test_unconstrained_child_object_demand_retains_every_profile() -> None:
    source = _source()

    assert "broad_profile AS" in source
    assert "No kind/role/factor constraint means every profile is requestable" in source
    assert "CROSS JOIN profile_base AS profile" in source
    assert "WHERE required.demand_id IS NULL" in source


def test_parent_reducer_patch_replaces_only_recognised_correlated_retention_block() -> (
    None
):
    source = _source()

    assert "procedure.prosrc" in source
    assert "rebuild_numeric_pnf_parent_frontier_canonical" in source
    assert (
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_canonical("
        in source
    )
    assert "DELETE FROM execution.semantic_pnf_actor_profile AS profile" in source
    assert "indexed_numeric_pnf_demanded_actor_profiles" in source
    assert "JOIN execution.semantic_pnf_interface_export AS demand_export" in source
    assert "demand.expected_target_kind = 1" in source
    assert "demand.expected_object_kind_symbol_id IS NULL" in source
    assert "demand.role_symbol_id IS NULL" in source
    assert "demand.expected_factor_type_symbol_id IS NULL" in source
    assert "refuses to replace an unrecognised actor-retention implementation" in source
