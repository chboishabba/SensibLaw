from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/146_delta_demand_planning.sql"


def test_full_and_delta_schedulers_share_one_demand_kernel() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "plan_numeric_pnf_one_demand" in sql
    assert sql.count("execution.plan_numeric_pnf_one_demand(") >= 2
    assert "plan_numeric_pnf_demand_candidates_for_interfaces" in sql


def test_delta_scheduler_covers_existing_provenance_and_new_eligibility() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    delta = sql.split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_for_interfaces",
        1,
    )[1].split("CREATE OR REPLACE FUNCTION execution.plan_demands_after_global_lookup_refresh", 1)[0]
    assert "existing.source_interface_id = ANY(selected_interface_ids)" in delta
    assert "global.interface_id = ANY(selected_interface_ids)" in delta
    assert "global.target_kind = demand.expected_target_kind" in delta
    assert "global.key_kind = 1" in delta
    assert "global.key_kind = 2" in delta
    assert "global.key_kind = 3" in delta
    assert "global.key_kind = 5" in delta


def test_delta_insert_suppresses_full_trigger_then_runs_sparse_planner() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "sensiblaw.delta_global_lookup_refresh" in sql
    trigger = sql.split(
        "CREATE OR REPLACE FUNCTION execution.plan_demands_after_global_lookup_refresh",
        1,
    )[1].split("CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_interfaces", 1)[0]
    assert "current_setting('sensiblaw.delta_global_lookup_refresh', TRUE) = 'on'" in trigger

    refresh = sql.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_pnf_global_lookup_interfaces",
        1,
    )[1]
    assert "set_config('sensiblaw.delta_global_lookup_refresh', 'on', TRUE)" in refresh
    assert "plan_numeric_pnf_demand_candidates_for_interfaces" in refresh


def test_delta_planner_iterates_affected_demand_ids_not_all_document_demands() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "FOREACH selected_demand_id IN ARRAY affected_ids LOOP" in sql
    assert "ARRAY[]::BIGINT[]" in sql
