from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M096 = ROOT / "database/postgres_migrations/096_late_external_demand_planner.sql"
M097 = ROOT / "database/postgres_migrations/097_external_evidence_projection_and_wakeup.sql"
M098 = ROOT / "database/postgres_migrations/098_external_demand_hardening_and_receipts.sql"
M099 = ROOT / "database/postgres_migrations/099_external_fact_axis_reuse.sql"
M100 = ROOT / "database/postgres_migrations/100_external_provider_boundary_projection.sql"
M101 = ROOT / "database/postgres_migrations/101_literal_provider_call_receipts.sql"
M103 = ROOT / "database/postgres_migrations/103_external_source_freshness_and_snapshot_provenance.sql"
M104 = ROOT / "database/postgres_migrations/104_external_freshness_lease_projection.sql"
M105 = ROOT / "database/postgres_migrations/105_monotone_external_candidate_fibres.sql"
M106 = ROOT / "database/postgres_migrations/106_exact_external_freshness_recompute.sql"
M107 = ROOT / "database/postgres_migrations/107_lease_aware_external_completion.sql"
M108 = ROOT / "database/postgres_migrations/108_freshness_filtered_external_projection.sql"
M109 = ROOT / "database/postgres_migrations/109_current_external_context_projection.sql"
M110 = ROOT / "database/postgres_migrations/110_late_external_demand_planner_fix.sql"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_planner_is_h9_only_and_consumer_scoped() -> None:
    sql = _sql(M096)
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer", 1
    )[1].split("$$;", 1)[0]
    assert "work.horizon=9 AND work.work_state=1" in body
    assert "selected_consumer_ref" in body
    assert "selected_query_ref" in body
    assert "numeric_pnf_consumer_stop_at_horizon" in body
    assert "semantic_parser_token" not in body


def test_external_requests_deduplicate_before_provider_leasing() -> None:
    sql = _sql(M096)
    assert "request_digest BYTEA NOT NULL UNIQUE" in sql
    assert "ensure_numeric_pnf_external_request" in sql
    claim = sql.split(
        "CREATE OR REPLACE FUNCTION execution.claim_numeric_pnf_external_provider_batch", 1
    )[1].split("$$;", 1)[0]
    assert "refresh_numeric_pnf_external_request_cache_state" in claim
    assert "FOR UPDATE SKIP LOCKED" in claim
    assert "request_state=3" in claim


def test_property_enrichment_is_axis_and_property_specific() -> None:
    sql = _sql(M096) + _sql(M098)
    assert "provider_property_numeric_id" in sql
    assert "axis_kind" in sql
    assert "property need requires positive property id and axis" in sql
    assert "semantic_pnf_consumer_external_need_identity_idx" in sql
    assert "COALESCE(axis_kind,0)" in sql
    assert "COALESCE(provider_property_numeric_id,0)" in sql


def test_contextual_external_evidence_has_no_identity_promotion_path() -> None:
    sql = _sql(M097) + _sql(M099) + _sql(M109)
    assert "semantic_pnf_world_candidate_requirement" in sql
    assert "materialize_numeric_pnf_external_context_for_request" in sql
    assert "admit_numeric_pnf_external_identity_alignment" not in sql
    assert "semantic_pnf_identity_witness" not in sql


def test_expired_provider_lease_is_cache_probed_before_retry() -> None:
    sql = _sql(M098)
    refresh = sql.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_external_request_cache_state", 1
    )[1].split("$$;", 1)[0]
    assert "request.request_state=4 AND request.lease_expires_at<CURRENT_TIMESTAMP" in refresh
    assert "request_state=2" in refresh
    assert "request_state=3" in refresh


def test_provider_evidence_is_immutable_and_call_counts_are_empirical() -> None:
    sql = _sql(M098) + _sql(M099) + _sql(M101) + _sql(M108)
    recorder = sql.split(
        "CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_external_evidence", 1
    )[-1].split("$$;", 1)[0]
    assert "ON CONFLICT(evidence_digest) DO NOTHING" in recorder
    assert "DO UPDATE SET request_id" not in recorder
    assert "semantic_pnf_external_provider_batch_receipt" in sql
    assert "fresh_provider_calls" in sql
    assert "requests_per_provider_call" in sql
    assert "logical provider-boundary evaluations" in _sql(M101)


def test_provider_claim_projects_only_external_boundary_identifiers() -> None:
    sql = _sql(M100)
    claim = sql.split(
        "CREATE FUNCTION execution.claim_numeric_pnf_external_provider_batch", 1
    )[1].split("$$;", 1)[0]
    assert "label.symbol_text" in claim
    assert "subject.provider_numeric_id" in claim
    assert "label_symbol_id BIGINT" not in sql.split("RETURNS TABLE", 1)[1].split(") LANGUAGE", 1)[0]
    assert "world_entity_id BIGINT" not in sql.split("RETURNS TABLE", 1)[1].split(") LANGUAGE", 1)[0]


def test_freshness_cache_probe_is_source_epoch_sensitive() -> None:
    sql = _sql(M103)
    assert "minimum_source_epoch BIGINT" in sql
    refresh = sql.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_external_request_cache_state", 1
    )[1].split("$$;", 1)[0]
    assert "candidate.source_epoch>=request.minimum_source_epoch" in refresh
    assert "evidence.source_epoch>=request.minimum_source_epoch" in refresh


def test_freshness_lease_preserves_provider_native_boundary() -> None:
    sql = _sql(M104)
    return_table = sql.split("RETURNS TABLE", 1)[1].split(") LANGUAGE", 1)[0]
    assert "label_text TEXT" in return_table
    assert "provider_subject_numeric_id BIGINT" in return_table
    assert "provider_property_numeric_id BIGINT" in return_table
    assert "minimum_source_epoch BIGINT" in return_table
    assert "label_symbol_id BIGINT" not in return_table
    assert "world_entity_id BIGINT" not in return_table
    body = sql.split(
        "CREATE FUNCTION execution.claim_numeric_pnf_external_provider_batch", 1
    )[1].split("$$;", 1)[0]
    assert "label.symbol_text" in body
    assert "subject.provider_numeric_id" in body
    assert "leased.minimum_source_epoch" in body


def test_candidate_discovery_is_monotone_and_unknown_age_cannot_replace_known_age() -> None:
    sql = _sql(M105)
    assert "upsert_numeric_pnf_label_world_candidate" in sql
    assert "DELETE FROM execution.semantic_pnf_label_world_candidate" not in sql
    assert "DROP CONSTRAINT" in sql
    upsert = sql.split(
        "CREATE OR REPLACE FUNCTION execution.upsert_numeric_pnf_label_world_candidate", 1
    )[1].split("$$;", 1)[0]
    assert "EXCLUDED.source_epoch IS NOT NULL" in upsert
    assert "EXCLUDED.source_epoch>=execution.semantic_pnf_label_world_candidate.source_epoch" in upsert
    assert "OR EXCLUDED.source_epoch IS NULL" not in upsert


def test_freshness_recomputes_exact_active_member_max_and_handles_property_to_discovery_fan_in() -> None:
    sql = _sql(M106)
    recompute = sql.split(
        "CREATE OR REPLACE FUNCTION execution.recompute_numeric_pnf_external_request_freshness", 1
    )[1].split("$$;", 1)[0]
    assert "max(need.minimum_source_epoch)" in recompute
    assert "request.request_kind=1 AND need.need_kind IN (1,2)" in recompute
    assert "request.request_kind=2 AND need.need_kind=2" in recompute
    assert "new_floor IS DISTINCT FROM old_floor" in recompute
    assert "old_state=4" in recompute
    assert "AFTER UPDATE OF minimum_source_epoch,active" in sql


def test_external_evidence_persistence_does_not_complete_or_wake_request() -> None:
    sql = _sql(M108)
    recorder = sql.split(
        "CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_external_evidence", 1
    )[1].split("$$;", 1)[0]
    assert "request_state=5" not in recorder
    assert "wake_numeric_pnf_external_request_members" not in recorder
    assert "materialize_numeric_pnf_external_context_for_request" not in recorder


def test_completion_is_lease_freshness_aware_and_only_then_wakes_h9() -> None:
    sql = _sql(M108)
    complete = sql.split(
        "CREATE OR REPLACE FUNCTION execution.complete_numeric_pnf_external_request", 1
    )[1].split("$$;", 1)[0]
    assert "current_floor IS DISTINCT FROM leased_minimum_source_epoch" in complete
    assert "freshness-contract-changed-during-lease" in complete
    assert "materialize_numeric_pnf_external_context_for_request" in complete
    assert "wake_numeric_pnf_external_request_members" in complete


def test_active_external_context_projection_uses_newest_admissible_epoch_only() -> None:
    sql = _sql(M109)
    materialize = sql.split(
        "CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_for_request", 1
    )[1].split("$$;", 1)[0]
    assert "max(evidence.source_epoch)" in materialize
    assert "evidence.source_epoch>=request.minimum_source_epoch" in materialize
    assert "evidence.source_epoch=selected_epoch" in materialize
    assert "DELETE FROM execution.semantic_pnf_world_candidate_requirement" in materialize
    assert "provider_property_numeric_id=request.provider_property_numeric_id" in materialize
    assert "Manual/static candidate requirements and cold" in sql


def test_external_planner_fix_avoids_record_shadowing_and_short_circuits_empty_need_sets() -> None:
    sql = _sql(M110)
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.plan_numeric_pnf_external_demands_for_consumer", 1
    )[1].split("$$;", 1)[0]
    assert "DECLARE external_need RECORD" in body
    assert "FOR external_need IN" in body
    assert "SELECT need_row.*,demand.lexical_symbol_id,demand.source_object_id" in body
    assert "SELECT need.*,demand.lexical_symbol_id,demand.source_object_id" not in body
    assert "IF NOT EXISTS (" in body
    assert "RETURN 0;" in body
    assert "6::smallint" in body
    assert "external_need.need_kind" in body
    assert "external_need.lexical_symbol_id" in body
