from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "postgres_migrations" / "209_wire_relation_delta_candidate_reconciler.sql"


def test_209_wires_parent_reconciler_and_fails_closed() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "reconcile_numeric_pnf_parent_candidates" in sql
    assert "pg_get_functiondef" in sql
    assert "canonical markers absent" in sql
    assert "reduce_numeric_pnf_parent_frontier_affected(bigint)" in sql


def test_209_does_not_add_a_second_candidate_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "DELETE FROM execution.semantic_pnf_demand_candidate" in sql
    assert "INSERT INTO execution.semantic_pnf_demand_candidate" in sql
    assert "semantic_relation_reconciliation_receipt" in sql
    assert "execution.plan_numeric_pnf_demand_candidates_ids" not in sql



def test_209_replacement_is_only_shared_reconciler_call() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    replacement = sql.split("replacement TEXT :=", 1)[1].split("BEGIN", 1)[0]

    assert "reconcile_numeric_pnf_parent_candidates" in replacement
    assert "DELETE FROM execution.semantic_pnf_demand_candidate" not in replacement
    assert "INSERT INTO execution.semantic_pnf_demand_candidate" not in replacement


def test_209_receipt_owner_is_the_active_parent_candidate_phase() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert (
        "'execution.reduce_numeric_pnf_parent_frontier_affected.candidates'"
        in sql
    )
    assert "'none'" in sql
