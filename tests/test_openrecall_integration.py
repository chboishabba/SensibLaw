from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.openrecall_import import ensure_openrecall_capture_schema, import_openrecall_db, load_openrecall_units
from src.reporting.structure_report import TextUnit
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


def _seed_openrecall_db(tmp_path: Path, *, timestamp: int) -> tuple[Path, Path]:
    storage_dir = tmp_path / "openrecall"
    storage_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = storage_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    (screenshot_dir / f"{timestamp}.webp").write_bytes(b"fake-image")
    source_db = storage_dir / "recall.db"
    with sqlite3.connect(source_db) as conn:
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
            (
                "Firefox",
                "Notification routing feature PR",
                "Please implement the notification routing feature before Friday close of business.",
                timestamp,
                b"embed",
            ),
        )
        conn.commit()
    return source_db, storage_dir


def test_openrecall_import_normalizes_capture_rows_and_units(tmp_path: Path) -> None:
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(tmp_path, timestamp=source_ts)
    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        summary = import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-test-v1",
        )
        conn.commit()
        assert summary.source_entry_count == 1
        assert summary.imported_capture_count == 1
        row = conn.execute(
            """
            SELECT app_name, window_title, ocr_text, screenshot_path, embedding_present, captured_date
            FROM openrecall_capture_sources
            """
        ).fetchone()
        assert row is not None
        assert row["app_name"] == "Firefox"
        assert row["window_title"] == "Notification routing feature PR"
        assert "notification routing feature" in row["ocr_text"].casefold()
        assert row["screenshot_path"].endswith(".webp")
        assert row["embedding_present"] == 1
        unit_row = conn.execute("SELECT text FROM openrecall_capture_text_units").fetchone()
        assert unit_row is not None
        assert "[Firefox]" in str(unit_row["text"])
        assert "Notification routing feature PR" in str(unit_row["text"])

    units = load_openrecall_units(itir_db, import_run_id="openrecall-test-v1")
    assert len(units) == 1
    assert units[0].source_type == "openrecall_capture"
    assert "notification routing feature" in units[0].text.casefold()


def test_mission_lens_report_includes_openrecall_actual_rows(tmp_path: Path) -> None:
    from scripts.mission_lens import build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(tmp_path, timestamp=source_ts)
    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"

    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_openrecall_capture_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
            TextUnit("m2", "chat-a", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-openrecall-v1")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-import:mission-lens",
        )
        conn.commit()

    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [
                {"ts": "2026-03-08T11:00:00Z", "hour": 11, "kind": "shell", "detail": "General shell work"},
            ],
            "frequency_by_hour": {"shell": [0] * 11 + [1] + [0] * 12},
        },
    )

    report = build_mission_lens_report(
        itir_db_path=itir_db,
        sb_db_path=sb_db,
        date="2026-03-08",
        run_id="mission-lens-openrecall-v1",
    )
    assert report["summary"]["openrecall_activity_count"] == 1
    assert any(row["kind"] == "openrecall_capture" for row in report["openrecall_activity_rows"])
    assert any(row["kind"] == "openrecall_capture" for row in report["activity_rows"])
    openrecall_row = next(row for row in report["activity_rows"] if row["kind"] == "openrecall_capture")
    assert openrecall_row["mappingSource"] in {"lexical", "unmapped"}
    assert openrecall_row["meta"]["sourceKind"] == "openrecall_capture"
    assert any(node["id"] == "actual:openrecall_capture" for node in report["actual_allocation"]["left"])


def test_imported_openrecall_units_can_feed_transcript_semantic_pipeline(tmp_path: Path) -> None:
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(tmp_path, timestamp=source_ts)
    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_openrecall_capture_schema(conn)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-semantic-v1",
        )
        conn.commit()
    units = load_openrecall_units(itir_db, import_run_id="openrecall-semantic-v1")
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        result = run_transcript_semantic_pipeline(conn, units, run_id="openrecall-semantic-v1")
        report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
        conn.commit()

    assert units
    mission_summary = report.get("mission_observer", {}).get("summary", {})
    assert int(mission_summary.get("mission_count", 0)) >= 1
    assert any("notification routing feature" in unit.text.casefold() for unit in units)
