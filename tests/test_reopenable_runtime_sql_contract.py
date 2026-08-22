from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "postgres_migrations"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_087_preserves_candidate_state_v1_existing_column_order() -> None:
    sql = _sql("087_reopenable_runtime_hardening.sql")
    start = sql.index(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_state_v1 AS"
    )
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
    sql = _sql("088_progressive_reopenable_resolution.sql").lower()
    for verb in ("insert into", "update", "delete from"):
        assert f"{verb} execution.semantic_pnf_frontier_resolution" not in sql


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


def test_089_redeclares_expensive_parser_anchor_with_numeric_constants() -> None:
    sql = _sql("089_numeric_incremental_runtime_economy.sql")
    assert "semantic_pnf_hot_symbol_constant" in sql
    assert "token.pos_symbol_id IN (constant.propn_id, constant.noun_id)" in sql
    assert "token.dependency_symbol_id = constant.appos_id" in sql
    replacement = sql[
        sql.index(
            "CREATE OR REPLACE FUNCTION execution.numeric_pnf_document_parser_object_anchor"
        ) :
    ]
    assert "pos.symbol_text" not in replacement
    assert "dep.symbol_text" not in replacement


def test_090_identity_evidence_hot_joins_are_numeric() -> None:
    sql = _sql("090_numeric_parser_evidence_and_learning.sql")
    assert "entity.entity_type_symbol_id=constant.person_id" in sql
    assert "source_token.dependency_symbol_id=constant.appos_id" in sql
    assert "mention.pos_symbol_id=constant.propn_id" in sql
    assert "semantic_pnf_hot_cue_symbol" in sql
    function = sql[
        sql.index(
            "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_parser_identity_evidence"
        ) :
    ]
    assert "mention_pos.symbol_text" not in function
    assert "dependency.symbol_text" not in function
    assert "cue_text.symbol_text" not in function


def test_lazy_horizon_queue_only_advances_unresolved_deductive_work() -> None:
    sql = _sql("089_numeric_incremental_runtime_economy.sql")
    assert "semantic_pnf_horizon_work_queue" in sql
    assert "proof.outcome_state=2" in sql
    assert "proof.candidate_count=1" in sql
    # Inductive preference is never referenced as a settling condition here.
    function = sql[
        sql.index(
            "CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work"
        ) :
    ]
    assert (
        "semantic_pnf_candidate_preference"
        not in function.split("-- Reverse dependency graph", 1)[0]
    )


def test_no_evidence_cannot_become_refutation_by_incremental_wiring() -> None:
    sql = _sql("091_numeric_incremental_wiring.sql").lower()
    assert "admission_state=2" in sql  # positive cache maintenance is proof-bearing
    assert "candidate_admissibility_event" not in sql
    assert "refute" not in sql


def test_world_label_cache_is_many_candidate_not_scalar() -> None:
    sql = _sql("089_numeric_incremental_runtime_economy.sql")
    assert "PRIMARY KEY(label_symbol_id,world_entity_id)" in sql
    assert (
        "UNIQUE(label_symbol_id,world_entity_id)" not in sql
    )  # PK already permits many entities per label
    assert "UNIQUE(label_symbol_id,candidate_ordinal,cache_revision)" in sql


def test_hot_projection_is_rebuildable_from_append_only_history() -> None:
    sql89 = _sql("089_numeric_incremental_runtime_economy.sql")
    sql91 = _sql("091_numeric_incremental_wiring.sql")
    assert "rebuild_numeric_pnf_candidate_current_state" in sql89
    assert "verify_numeric_pnf_candidate_current_state" in sql91
    assert "semantic_pnf_candidate_latest_execution" in sql91


def test_frequency_codebook_never_replaces_canonical_symbol_id() -> None:
    sql = _sql("089_numeric_incremental_runtime_economy.sql")
    assert "semantic_symbol_frequency_codebook" in sql
    assert "symbol_id BIGINT NOT NULL" in sql
    assert "physical_code BIGINT NOT NULL" in sql
    assert "UPDATE execution.semantic_symbol" not in sql


def test_learning_nonincrease_requires_same_token_workload() -> None:
    sql = _sql("090_numeric_parser_evidence_and_learning.sql")
    assert "learning comparison requires same token workload" in sql
    assert (
        "after_row.unresolved_resolution_work<=before_row.unresolved_resolution_work"
        in sql
    )
