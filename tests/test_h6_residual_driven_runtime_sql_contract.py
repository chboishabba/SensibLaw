from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M110 = ROOT / "database/postgres_migrations/110_residual_driven_h6_and_zero_need_h9.sql"


def _sql() -> str:
    return M110.read_text(encoding="utf-8")


def _function(sql: str, name: str) -> str:
    return sql.split(f"CREATE OR REPLACE FUNCTION execution.{name}", 1)[1].split(
        "$$;", 1
    )[0]


def test_h6_is_numeric_typed_factor_evidence_not_proximity_or_text_matching() -> None:
    body = _function(
        _sql(),
        "refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer",
    )
    assert "semantic_pnf_hyperedge" in body
    assert "semantic_pnf_factor" in body
    assert "factor_type_symbol_id" in body
    assert "predicate_symbol_id" in body
    assert "role_symbol_id" in body
    assert "candidate_factor.temporal_state" in body
    assert "matched.candidate_temporal_state=matched.source_temporal_state" in body
    assert "semantic_symbol" not in body
    assert "symbol_text" not in body
    assert "regexp" not in body.lower()
    assert "~" not in body
    assert " LIKE " not in body.upper()


def test_h6_missing_relation_cannot_create_negative_evidence() -> None:
    body = _function(
        _sql(),
        "refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer",
    )
    assert "2,6" in body  # evidence family 2, H6
    assert "1::BIGINT AS signed_residual" in body
    assert "-1::BIGINT AS signed_residual" not in body
    assert (
        "NOT EXISTS" in body
    )  # only proof/stop guards, never a negative-evidence producer
    assert "h6_discourse_factor_role_signature" in body
    assert "h6_temporal_factor_role_signature" in body


def test_h6_compares_distinct_signatures_before_persistence() -> None:
    body = _function(
        _sql(),
        "refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer",
    )
    assert "source_signature AS MATERIALIZED" in body
    assert "SELECT DISTINCT" in body
    assert "matched AS MATERIALIZED" in body
    assert "state.target_id<>ready.source_object_id" in body
    assert "expected_factor_type_symbol_id" in body
    assert "ready.role_symbol_id" in body


def test_h6_uses_smallint_horizon_argument_for_existing_stop_function() -> None:
    body = _function(
        _sql(),
        "refresh_numeric_pnf_h6_discourse_temporal_evidence_for_consumer",
    )
    assert "selected_policy_ref,3::smallint" in body


def test_zero_signed_h3_coordinate_is_classified_neutral_not_resolved() -> None:
    sql = _sql()
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_candidate_evidence_classification_v1",
        1,
    )[1].split(";", 1)[0]
    assert "signed_residual > 0 THEN 2" in view
    assert "signed_residual < 0 THEN 3" in view
    assert "universe.demand_id IS NOT NULL THEN 1" in view
    assert "proof" not in view.lower()
    assert "resolved" not in view.lower()


def test_queue_processing_and_semantic_outcome_are_distinct() -> None:
    sql = _sql()
    assert "semantic_pnf_consumer_horizon_outcome" in sql
    refresh = _function(sql, "refresh_numeric_pnf_consumer_horizon_outcome")
    assert "state.proof_unique THEN 4" in refresh
    assert "state.consumer_sufficient THEN 3" in refresh
    assert "state.evidence_count=0 THEN 1" in refresh
    assert "NOT state.proof_unique AND NOT state.consumer_sufficient" in refresh


def test_next_horizon_contains_only_semantic_residual() -> None:
    body = _function(_sql(), "advance_numeric_pnf_horizon_work_for_consumer")
    assert "outcome.residual_required" in body
    assert "AND NOT outcome.residual_required" in body
    assert "DELETE FROM execution.semantic_pnf_consumer_horizon_work_queue" in body
    assert "ON CONFLICT(demand_id,consumer_ref,query_ref,policy_ref,horizon)" in body


def test_h9_zero_need_is_successful_zero_work_and_needs_remain_explicit() -> None:
    body = _function(_sql(), "plan_numeric_pnf_external_demands_for_consumer")
    assert "IF NOT EXISTS" in body
    assert "semantic_pnf_consumer_external_need AS external_need" in body
    assert "RETURN 0" in body
    assert "work.horizon=9 AND work.work_state=1" in body
    assert "FOR need_row IN" in body
    assert "DECLARE need_row RECORD" in body
    assert "DECLARE need RECORD" not in body


def test_h9_funnel_does_not_equate_ready_work_with_external_need() -> None:
    sql = _sql()
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_consumer_horizon_funnel_v1", 1
    )[1]
    assert "explicit_external_need_rows" in view
    assert "semantic_pnf_consumer_external_need" in view
    assert "need.active" in view
