from __future__ import annotations

import sqlite3

from sensiblaw.db import ContextFieldDAO, MigrationRunner
from sensiblaw.ingest.les_adapter import import_les_snapshot


def test_import_les_snapshot_stores_environment_overlay():
    conn = sqlite3.connect(":memory:")
    MigrationRunner(conn).apply_all()

    snapshot = {
        "snapshot_id": "les_2026_02_06T00Z",
        "captured_at": "2026-02-06T00:00:00Z",
        "location": "lat,lon",
        "environment_state": {"season": ["Makuru", "late-winter"], "heat_load": "low"},
        "models": {"season_model": "v1.0"},
    }
    import_les_snapshot(conn, snapshot)

    dao = ContextFieldDAO(conn)
    rec = dao.get("les:les_2026_02_06T00Z")
    assert rec is not None
    assert rec.context_type == "les_environment"
    assert rec.payload["heat_load"] == "low"
    assert rec.provenance["models"]["season_model"] == "v1.0"
    assert rec.symbolic is False
