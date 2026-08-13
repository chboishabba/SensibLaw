from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M114 = ROOT / "database/postgres_migrations/114_dormant_external_request_reprobe.sql"


def test_reactivated_dormant_request_is_cache_probed_before_wakeup() -> None:
    sql = M114.read_text(encoding="utf-8")
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.wake_numeric_pnf_external_cache_hits", 1
    )[1].split("$$;", 1)[0]
    observer = body.index("refresh_numeric_pnf_external_request_observer_state")
    cache = body.index("refresh_numeric_pnf_external_request_cache_state")
    scan = body.index("request.request_state=2")
    assert observer < cache < scan
    assert "semantic_pnf_external_request_active_member_v1" in body
