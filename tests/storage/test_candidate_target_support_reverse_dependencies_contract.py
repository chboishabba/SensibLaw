from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SQL = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "167_candidate_target_support_reverse_dependencies.sql"
).read_text(encoding="utf-8")


def test_candidate_and_support_write_orders_are_both_covered() -> None:
    assert "REFERENCING NEW TABLE AS inserted_candidate" in SQL
    assert "REFERENCING NEW TABLE AS inserted_object_support" in SQL
    assert "REFERENCING NEW TABLE AS inserted_factor_support" in SQL
    assert SQL.count("FOR EACH STATEMENT") == 3
    assert "FOR EACH ROW" not in SQL


def test_object_and_factor_target_support_are_reverse_indexed() -> None:
    assert "candidate.target_kind=1" in SQL
    assert "support.object_id=candidate.target_id" in SQL
    assert "candidate.target_kind=2" in SQL
    assert "support.factor_id=candidate.target_id" in SQL
    assert "SELECT 1,support.token_id,candidate.demand_id,2" in SQL


def test_upgrade_backfills_both_target_kinds() -> None:
    assert SQL.count("FROM execution.semantic_pnf_demand_candidate AS candidate") >= 2
    assert "JOIN execution.semantic_pnf_object_token_support AS support" in SQL
    assert "JOIN execution.semantic_pnf_factor_token_support AS support" in SQL


def test_reverse_edges_are_conservative_not_semantic_refutations() -> None:
    assert "Missing reverse edges can make incremental" in SQL
    assert "conservative stale/extra edges merely over-wake" in SQL
    assert "semantic_pnf_candidate_admissibility_event" not in SQL
    assert "semantic_pnf_frontier_resolution" not in SQL
