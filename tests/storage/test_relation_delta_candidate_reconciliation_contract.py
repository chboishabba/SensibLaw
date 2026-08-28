from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "postgres_migrations" / "208_relation_delta_candidate_reconciliation.sql"
SYMBOL_STORE = ROOT / "src" / "storage" / "postgres" / "numeric_symbol_store.py"
APPLIER = ROOT / "scripts" / "apply_pg_migrations.sh"


def test_candidate_planner_materializes_desired_then_diffs_current() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "pg_temp.semantic_pnf_desired_candidate" in sql
    assert "unchanged_rows_skipped" in sql
    assert "semantic_relation_reconciliation_receipt" in sql
    assert "NOT EXISTS (" in sql
    assert "desired.target_kind = candidate.target_kind" in sql
    assert "desired.candidate_score IS NOT DISTINCT FROM candidate.candidate_score" in sql
    assert "semantic_authority_effect" in sql
    assert "RETURN inserted_total" in sql


def test_candidate_reconciliation_does_not_start_with_unconditional_fibre_delete() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    function = sql.split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_demand_candidates_ids", 1
    )[1]
    desired_pos = function.index("INSERT INTO pg_temp.semantic_pnf_desired_candidate")
    delete_pos = function.index("DELETE FROM execution.semantic_pnf_demand_candidate")

    assert desired_pos < delete_pos
    assert "AND NOT EXISTS (" in function[delete_pos:]


def test_symbol_interning_acquires_deterministic_transaction_locks() -> None:
    source = SYMBOL_STORE.read_text(encoding="utf-8")

    assert "pg_advisory_xact_lock" in source
    assert "hashtextextended" in source
    assert source.count("ORDER BY kind_id, symbol_text") >= 2


def test_migration_applier_runs_runtime_preflight_before_psql_schema_write() -> None:
    source = APPLIER.read_text(encoding="utf-8")

    audit_pos = source.index("audit_pg_migration_runtime.py")
    schema_pos = source.index("CREATE TABLE IF NOT EXISTS public.sensiblaw_schema_migration")
    assert audit_pos < schema_pos
