from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_087_preserves_candidate_state_v1_existing_column_order() -> None:
    sql = _sql("087_reopenable_runtime_hardening.sql")
    start = sql.index("CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_state_v1 AS")
    end = sql.index(";", start)
    view = sql[start:end]
    required_order = (
        "universe.demand_id",
        "universe.target_kind",
        "universe.target_id",
        "TRUE AS represented_possible",
        "AS active",
        "AS execution_residual",
        "AS refuted",
        "AS admissible",
        "execution_state.reason_ref AS execution_reason_ref",
        "admissibility.evidence_id AS admissibility_evidence_id",
        "current_candidate.demand_id IS NOT NULL AS current_planner_member",
    )
    positions = [view.index(fragment) for fragment in required_order]
    assert positions == sorted(positions)


def test_progressive_resolver_never_writes_frontier_resolution() -> None:
    sql = _sql("088_progressive_reopenable_resolution.sql")
    lowered = sql.lower()
    assert "insert into execution.semantic_pnf_frontier_resolution" not in lowered
    assert "update execution.semantic_pnf_frontier_resolution" not in lowered
    assert "delete from execution.semantic_pnf_frontier_resolution" not in lowered


def test_progressive_resolver_keeps_preference_distinct_from_proof() -> None:
    sql = _sql("088_progressive_reopenable_resolution.sql")
    assert "AS deductive_unique" in sql
    assert "AS preference_only" in sql
    assert "'inductive_preference'" in sql
    assert "'deductive_unique'" in sql


def test_horizons_are_one_candidate_fibre_not_three_candidate_generators() -> None:
    sql = _sql("088_progressive_reopenable_resolution.sql")
    assert "semantic_pnf_candidate_horizon_state_v1" in sql
    assert "fibre_cardinality_invariant" in sql
    assert "count(DISTINCT represented_count) = 1" in sql


def test_runtime_history_is_append_only_by_corrective_event() -> None:
    sql = _sql("087_reopenable_runtime_hardening.sql")
    for relation in (
        "semantic_pnf_candidate_evidence",
        "semantic_pnf_candidate_execution_event",
        "semantic_pnf_candidate_admissibility_event",
        "semantic_pnf_candidate_preference",
        "semantic_pnf_demand_candidate_observation",
    ):
        assert f"BEFORE UPDATE ON execution.{relation}" in sql
