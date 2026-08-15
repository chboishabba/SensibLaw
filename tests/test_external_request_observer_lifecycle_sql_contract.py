from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M113 = ROOT / "database/postgres_migrations/113_external_request_observer_lifecycle.sql"


def _sql() -> str:
    return M113.read_text(encoding="utf-8")


def _function(sql: str, name: str) -> str:
    return sql.split(f"CREATE OR REPLACE FUNCTION execution.{name}", 1)[1].split(
        "$$;", 1
    )[0]


def test_dormant_request_is_distinct_from_cache_hit_and_blocked() -> None:
    sql = _sql()
    assert "request_state IN (1,2,3,4,5,6,7,8)" in sql
    assert "8 dormant: no active semantic observer" in sql
    body = _function(sql, "refresh_numeric_pnf_external_request_observer_state")
    assert "SET request_state=8" in body
    assert "no-active-semantic-observer" in body
    assert "request.request_state<>5" in body


def test_active_member_requires_current_active_semantic_need() -> None:
    sql = _sql()
    view = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_external_request_active_member_v1",
        1,
    )[1].split(";", 1)[0]
    assert "semantic_pnf_consumer_external_need AS need" in view
    assert "need.active" in view
    assert "need.provider_id=request.provider_id" in view
    assert "request.request_kind=2" in view
    assert "need.axis_kind=request.axis_kind" in view
    assert (
        "need.provider_property_numeric_id=request.provider_property_numeric_id" in view
    )


def test_completion_does_not_project_or_wake_after_observer_withdrawal() -> None:
    body = _function(_sql(), "complete_numeric_pnf_external_request")
    observer_guard = body.index("IF NOT EXISTS")
    materialize = body.index("materialize_numeric_pnf_external_context_for_request")
    wake = body.index("wake_numeric_pnf_external_request_members")
    assert observer_guard < materialize < wake
    assert "request_state=8" in body
    assert "RETURN FALSE" in body


def test_wakeup_uses_active_member_projection_only() -> None:
    body = _function(_sql(), "wake_numeric_pnf_external_request_members")
    assert "semantic_pnf_external_request_active_member_v1" in body
    assert "semantic_pnf_external_request_member AS member" not in body


def test_cache_hit_wakeup_is_observer_indexed() -> None:
    body = _function(_sql(), "wake_numeric_pnf_external_cache_hits")
    assert "refresh_numeric_pnf_external_request_observer_state" in body
    assert "semantic_pnf_external_request_active_member_v1" in body
    assert "request.request_state=2" in body


def test_dormant_requests_are_observable_separately() -> None:
    sql = _sql()
    assert "semantic_pnf_external_call_economy_v2" in sql
    assert "dormant_requests" in sql
    assert "request_state=8" in sql
