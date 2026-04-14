from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

from src.reporting.observation_lanes import (
    clear_observation_lane_registry_for_tests,
    get_observation_lanes,
    load_observation_activity_rows,
    load_observation_import_runs,
    load_observation_units,
    build_observation_summary,
    query_observation_captures,
)
from src.reporting.openrecall_import import (
    ensure_openrecall_capture_schema,
    import_openrecall_db,
    load_openrecall_import_runs,
    load_openrecall_activity_rows,
    load_openrecall_units,
    build_openrecall_capture_summary,
    query_openrecall_captures,
)
from src.reporting.worldmonitor_import import (
    ensure_worldmonitor_capture_schema,
    import_worldmonitor_data,
    load_worldmonitor_import_runs,
    load_worldmonitor_activity_rows,
    load_worldmonitor_units,
    build_worldmonitor_capture_summary,
    query_worldmonitor_captures,
)


def _seed_openrecall_db(tmp_path: Path, *, timestamp: int, text: str) -> tuple[Path, Path]:
    db_path = tmp_path / "recall.db"
    storage_dir = tmp_path / "openrecall_storage"
    screenshot_dir = storage_dir / "screenshots"
    storage_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    (screenshot_dir / f"{timestamp}.webp").write_bytes(b"fake-image")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              app TEXT,
              title TEXT,
              text TEXT,
              timestamp INTEGER UNIQUE,
              embedding BLOB
            )
            """
        )
        conn.execute(
            """
            INSERT INTO entries(app, title, text, timestamp, embedding)
            VALUES (?,?,?,?,?)
            """,
            ("Firefox", "Monitor thread", text, timestamp, b"embed"),
        )
        conn.commit()
    return db_path, storage_dir


def _seed_worldmonitor_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "worldmonitor"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.json").write_text(
        """{
  "source": "sample-source",
  "url": "https://example.org",
  "extracted": "2026-03-08",
  "cities": ["Example City"],
  "note": "sample row"
}""",
        encoding="utf-8",
    )
    return source_dir


def test_observation_lane_registry_is_boundaries_ready() -> None:
    lanes = get_observation_lanes()
    assert "openrecall" in lanes
    assert "worldmonitor" in lanes
    for key in ("openrecall", "worldmonitor"):
        lane = lanes[key]
        assert lane.key == key
        assert lane.source_unit_type
        assert lane.source_label
        for attr_name in (
            "ensure_schema",
            "import_data",
            "load_units",
            "load_activity_rows",
            "load_import_runs",
            "build_summary",
            "query_captures",
        ):
            assert callable(getattr(lane, attr_name))


def test_observation_lane_registry_loads_plugins_from_environment(tmp_path: Path, monkeypatch) -> None:
    plugin_path = tmp_path / "dummy_observation_lane_plugin.py"
    plugin_path.write_text(
        """
from pathlib import Path

from src.reporting.observation_lanes import ObservationLaneAdapter


def _no_op(conn):
    return None


def _load_units(db_path, **_kwargs):
    return []


def _load_activity_rows(conn, **_kwargs):
    return []


def _load_import_runs(conn, **_kwargs):
    return []


def _build_summary(conn, **_kwargs):
    return {}


def _query_captures(conn, **_kwargs):
    return []


dummy_lane = ObservationLaneAdapter(
    lane_key="dummy",
    source_unit_type="dummy_capture",
    source_label="Dummy Observer",
    ensure_schema=_no_op,
    import_data=_no_op,
    load_units=_load_units,
    load_activity_rows=_load_activity_rows,
    load_import_runs=_load_import_runs,
    build_summary=_build_summary,
    query_captures=_query_captures,
)


WIZ_OBSERVATION_LANE = dummy_lane
""".strip(),
        encoding="utf-8",
    )

    sys_path_before = list(sys.path)
    try:
        sys.path.insert(0, str(tmp_path))
        clear_observation_lane_registry_for_tests()
        monkeypatch.setenv("SENSIBLAW_OBSERVATION_LANE_MODULES", "dummy_observation_lane_plugin")
        lanes = get_observation_lanes()
    finally:
        sys.path[:] = sys_path_before
        clear_observation_lane_registry_for_tests()
        monkeypatch.delenv("SENSIBLAW_OBSERVATION_LANE_MODULES", raising=False)

    assert "dummy" in lanes


def test_observation_lane_contract_openrecall_adapter_roundtrip(tmp_path: Path) -> None:
    ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage = _seed_openrecall_db(tmp_path, timestamp=ts, text="Observer note for lane contract check.")
    itir_db = tmp_path / "itir.sqlite"

    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            import_run_id="contract-openrecall",
            storage_path=storage,
        )
        conn.commit()

        assert load_observation_units(
            itir_db,
            "openrecall",
            import_run_id="contract-openrecall",
        ) == load_openrecall_units(itir_db, import_run_id="contract-openrecall")
        assert load_observation_import_runs(conn, "openrecall") == load_openrecall_import_runs(conn)
        assert query_observation_captures(
            conn,
            "openrecall",
            import_run_id="contract-openrecall",
            source_kind="Firefox",
        ) == query_openrecall_captures(conn, import_run_id="contract-openrecall", app_name="Firefox")
        assert build_observation_summary(
            conn,
            "openrecall",
            import_run_id="contract-openrecall",
        ) == build_openrecall_capture_summary(conn, import_run_id="contract-openrecall")
        assert load_observation_activity_rows(conn, "openrecall", date="2026-03-08") == load_openrecall_activity_rows(
            conn,
            date="2026-03-08",
        )


def test_observation_lane_contract_worldmonitor_adapter_roundtrip(tmp_path: Path) -> None:
    source_dir = _seed_worldmonitor_dir(tmp_path)
    itir_db = tmp_path / "itir.sqlite"

    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_worldmonitor_capture_schema(conn)
        import_worldmonitor_data(conn, source_path=source_dir, import_run_id="contract-worldmonitor")
        conn.commit()

        assert load_observation_units(
            itir_db,
            "worldmonitor",
            import_run_id="contract-worldmonitor",
        ) == load_worldmonitor_units(itir_db, import_run_id="contract-worldmonitor")
        assert load_observation_import_runs(conn, "worldmonitor") == load_worldmonitor_import_runs(conn)
        assert query_observation_captures(
            conn,
            "worldmonitor",
            import_run_id="contract-worldmonitor",
            source_kind=None,
            text_query="sample",
        ) == query_worldmonitor_captures(conn, import_run_id="contract-worldmonitor", text_query="sample")
        assert build_observation_summary(
            conn,
            "worldmonitor",
            import_run_id="contract-worldmonitor",
        ) == build_worldmonitor_capture_summary(conn, import_run_id="contract-worldmonitor")
        assert len(load_observation_activity_rows(conn, "worldmonitor", date="2026-03-08")) > 0
        assert len(load_worldmonitor_activity_rows(conn, date="2026-03-08")) > 0
