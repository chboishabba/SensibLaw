from __future__ import annotations

import sqlite3

from sensiblaw.db import ContextFieldDAO, MigrationRunner
from sensiblaw.ingest.context_overlays import ingest_context_fields


def test_context_field_roundtrip():
    conn = sqlite3.connect(":memory:")
    MigrationRunner(conn).apply_all()
    dao = ContextFieldDAO(conn)

    overlay = {
        "context_id": "weather:test:2026-02-06T00Z",
        "context_type": "weather",
        "source": "bom.test",
        "time_start": "2026-02-06T00:00:00Z",
        "time_end": "2026-02-06T01:00:00Z",
        "payload": {"temp_c": 21.5, "wind_kmh": 12},
        "provenance": {"license": "test"},
        "symbolic": False,
    }
    ingest_context_fields(conn, [overlay])
    rec = dao.get("weather:test:2026-02-06T00Z")
    assert rec is not None
    assert rec.context_type == "weather"
    assert rec.symbolic is False
    assert rec.payload["temp_c"] == 21.5
    assert rec.provenance["license"] == "test"


def test_context_field_list_by_type():
    conn = sqlite3.connect(":memory:")
    ingest_context_fields(
        conn,
        [
            {"context_id": "m1", "context_type": "market", "payload": {"vix": 18.2}},
            {"context_id": "m2", "context_type": "market", "payload": {"vix": 19.1}},
            {"context_id": "w1", "context_type": "weather", "payload": {"temp_c": 30}},
        ],
    )
    dao = ContextFieldDAO(conn)
    markets = dao.list_by_type("market")
    assert len(markets) == 2
    assert all(r.context_type == "market" for r in markets)
