from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database/postgres_migrations/178_indexed_sparse_frontier_candidate_exposure.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_object_candidate_exposure_is_key_intersection_not_demand_profile_product() -> (
    None
):
    source = _source()

    assert (
        "CREATE OR REPLACE FUNCTION execution.indexed_numeric_pnf_object_candidate_rows("
        in source
    )
    assert "required_key AS MATERIALIZED" in source
    assert "profile_key AS MATERIALIZED" in source
    assert "matched_profile AS MATERIALIZED" in source
    assert "required.required_count = matched.matched_count" in source
    assert "JOIN profile_key AS profile" in source
    assert "CROSS JOIN profile_base AS profile" in source
    assert "WHERE required.demand_id IS NULL" in source


def test_exact_nullable_object_candidate_keys_are_preserved() -> None:
    source = _source()

    assert "constraint_row.key_kind IN (1, 2, 3, 4)" in source
    assert "profile.factor_type_symbol_id" in source
    assert "profile.object_kind_symbol_id" in source
    assert "profile.predicate_symbol_id" in source
    assert "profile.head_symbol_id" in source
    assert "profile.role_symbol_id" in source
    assert "SELECT DISTINCT" in source


def test_constraint_fibre_parity_is_fail_closed_before_indexed_execution() -> None:
    source = _source()

    assert "expected_key AS" in source
    assert "actual_key AS" in source
    assert "SELECT * FROM expected_key EXCEPT SELECT * FROM actual_key" in source
    assert "SELECT * FROM actual_key EXCEPT SELECT * FROM expected_key" in source
    assert "RAISE EXCEPTION" in source
    assert "object-demand constraint fibre disagrees" in source


def test_recency_scoring_and_candidate_coordinates_remain_the_migration_062_semantics() -> (
    None
):
    source = _source()

    assert "abs(demand.demand_position - profile.last_end_char)" in source
    assert "ln(1 + profile.occurrence_count)::DOUBLE PRECISION" in source
    assert "WHEN 1 THEN" in source
    assert "profile.first_start_char >= demand.source_region_start" in source
    assert "profile.last_end_char <= demand.source_region_end" in source
    assert "WHEN 2 THEN" in source
    assert "WHEN 3 THEN" in source
    assert "WHEN 4 THEN TRUE" in source
    assert "WHEN 5 THEN TRUE" in source
    assert "1::SMALLINT AS target_kind" in source
    assert "0::BIGINT AS index_rank" in source


def test_zero_constraint_demand_keeps_explicit_wildcard_semantics() -> None:
    source = _source()

    assert "broad_profile AS" in source
    assert "Absence of object-candidate constraints is not negative evidence" in source
    assert "LEFT JOIN required_count AS required" in source
    assert "CROSS JOIN profile_base AS profile" in source
    assert "WHERE required.demand_id IS NULL" in source


def test_migration_patches_only_recognised_object_candidate_cte_and_fails_closed() -> (
    None
):
    source = _source()

    assert "procedure.prosrc" in source
    assert "rebuild_numeric_pnf_parent_frontier_canonical" in source
    assert (
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier_canonical("
        in source
    )
    assert "object_candidate AS (" in source
    assert "factor_candidate AS (" in source
    assert "old_object_block" in source
    assert "JOIN execution.semantic_pnf_actor_profile AS profile" in source
    assert "demand.expected_object_kind_symbol_id IS NULL" in source
    assert "demand.lexical_symbol_id = object.head_symbol_id" in source
    assert "demand.lexical_symbol_id = profile.predicate_symbol_id" in source
    assert (
        "refuses to replace an unrecognised object-candidate implementation" in source
    )
    assert "indexed_numeric_pnf_object_candidate_rows" in source
