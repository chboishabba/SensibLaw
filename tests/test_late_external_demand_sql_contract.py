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
    sql = _sql(M097) + _sql(M099)
    assert "semantic_pnf_world_candidate_requirement" in sql
    assert "materialize_numeric_pnf_external_context_for_request" in sql
    assert "admit_numeric_pnf_external_identity_alignment" not in sql
    assert "semantic_pnf_identity_witness" not in sql


def test_cached_provider_fact_can_be_reprojected_to_later_consumer_axis() -> None:
    sql = _sql(M099)
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.materialize_numeric_pnf_external_context_for_request", 1
    )[1].split("$$;", 1)[0]
    assert "request.axis_kind" in body
    assert "evidence.provider_property_numeric_id=request.provider_property_numeric_id" in body
    wake = sql.split(
        "CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits", 1
    )[1].split("$$;", 1)[0]
    assert "materialize_numeric_pnf_external_context_for_request" in wake


def test_expired_provider_lease_is_cache_probed_before_retry() -> None:
    sql = _sql(M098)
    refresh = sql.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_external_request_cache_state", 1
    )[1].split("$$;", 1)[0]
    assert "request.request_state=4 AND request.lease_expires_at<CURRENT_TIMESTAMP" in refresh
    assert "request_state=2" in refresh
    assert "request_state=3" in refresh


def test_provider_evidence_is_immutable_and_call_counts_are_empirical() -> None:
    sql = _sql(M098) + _sql(M099) + _sql(M101)
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


def test_freshness_floor_is_strongest_member_requirement_and_cache_sensitive() -> None:
    sql = _sql(M103)
    assert "minimum_source_epoch BIGINT" in sql
    trigger = sql.split(
        "CREATE OR REPLACE FUNCTION execution.strengthen_numeric_pnf_external_request_freshness", 1
    )[1].split("$$;", 1)[0]
    assert "max(need.minimum_source_epoch)" in trigger
    assert "floor_value>minimum_source_epoch" in trigger
    assert "request_state IN (2,5)" in trigger
    setter = sql.split(
        "CREATE OR REPLACE FUNCTION execution.set_numeric_pnf_external_need_minimum_source_epoch", 1
    )[1].split("$$;", 1)[0]
    assert "semantic_pnf_external_request_member" in setter
    assert "selected_minimum_source_epoch>request.minimum_source_epoch" in setter
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
