from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M112 = ROOT / "database/postgres_migrations/112_consumer_observed_world_axis_contract.sql"


def _sql() -> str:
    return M112.read_text(encoding="utf-8")


def _function(sql: str, name: str) -> str:
    return sql.split(f"CREATE OR REPLACE FUNCTION execution.{name}", 1)[1].split("$$;", 1)[0]


def test_contract_cannot_select_all_h9_demands_implicitly() -> None:
    sql = _sql()
    assert "consumer world-axis contract requires at least one numeric demand selector" in sql
    table = sql.split("CREATE TABLE IF NOT EXISTS execution.semantic_pnf_consumer_world_axis_contract", 1)[1].split(";", 1)[0]
    assert "expected_target_kind IS NOT NULL" in table
    assert "expected_factor_type_symbol_id IS NOT NULL" in table
    assert "expected_object_kind_symbol_id IS NOT NULL" in table
    assert "lexical_symbol_id IS NOT NULL" in table
    assert "role_symbol_id IS NOT NULL" in table
    assert "residual_type_symbol_id IS NOT NULL" in table


def test_compiler_intersects_only_current_h9_residual() -> None:
    body = _function(_sql(), "compile_numeric_pnf_h9_external_needs_for_consumer")
    assert "semantic_pnf_consumer_horizon_work_queue" in body
    assert "work.horizon=9 AND work.work_state=1" in body
    assert "semantic_pnf_consumer_world_axis_contract_current_v1" in body
    assert "current_contract.active" in body
    assert "numeric_pnf_consumer_stop_at_horizon" in body
    assert "selected_policy_ref,6" in body


def test_compiler_matches_numeric_demand_coordinates_not_text() -> None:
    body = _function(_sql(), "compile_numeric_pnf_h9_external_needs_for_consumer")
    for coordinate in (
        "expected_target_kind",
        "expected_factor_type_symbol_id",
        "expected_object_kind_symbol_id",
        "lexical_symbol_id",
        "role_symbol_id",
        "residual_type_symbol_id",
    ):
        assert coordinate in body
    assert "semantic_symbol" not in body
    assert "symbol_text" not in body
    assert "regexp" not in body.lower()
    assert " LIKE " not in body.upper()


def test_empty_contract_set_compiles_zero_needs() -> None:
    body = _function(_sql(), "compile_numeric_pnf_h9_external_needs_for_consumer")
    assert "JOIN execution.semantic_pnf_consumer_world_axis_contract_current_v1" in body
    assert "SELECT count(DISTINCT need.need_id)::BIGINT INTO affected" in body
    assert "RETURN affected" in body


def test_contract_origins_do_not_override_manual_needs() -> None:
    sql = _sql()
    assert "semantic_pnf_consumer_external_need_origin" in sql
    assert "1 explicit/manual registration; 2 consumer world-axis contract" in sql
    body = _function(sql, "compile_numeric_pnf_h9_external_needs_for_consumer")
    assert "origin.origin_kind=2" in body
    assert "LEFT JOIN execution.semantic_pnf_consumer_external_need_origin AS origin" in body
    assert "COALESCE(bool_or(origin.active),FALSE)" in body


def test_freshness_and_priority_are_exact_over_active_origins() -> None:
    body = _function(_sql(), "recompute_numeric_pnf_external_need_from_origins")
    assert "min(origin.priority) FILTER (WHERE origin.active)" in body
    assert "max(origin.minimum_source_epoch) FILTER (WHERE origin.active)" in body
    assert "bool_or(origin.active)" in body


def test_property_contract_requires_explicit_axis_and_provider_property() -> None:
    sql = _sql()
    assert "property contract requires positive property id and axis" in sql
    assert "discovery/identity contract cannot carry property-axis coordinates" in sql


def test_funnel_keeps_h9_residual_separate_from_external_need() -> None:
    sql = _sql()
    view = sql.split("CREATE OR REPLACE VIEW execution.semantic_pnf_consumer_external_need_funnel_v1", 1)[1]
    assert "h9_residual_demands" in view
    assert "explicit_external_need_demands" in view
    assert "contract_external_need_demands" in view
    assert "active_external_need_rows" in view
