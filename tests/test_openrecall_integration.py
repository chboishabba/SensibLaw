from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.openrecall_import import (
    build_openrecall_capture_summary,
    ensure_openrecall_capture_schema,
    import_openrecall_db,
    load_openrecall_import_runs,
    load_openrecall_units,
    query_openrecall_captures,
)
from src.reporting.openrecall_raw_import import (
    ensure_openrecall_raw_row_schema,
    import_openrecall_raw_rows,
    load_openrecall_raw_import_runs,
    query_openrecall_raw_rows,
)
from src.reporting.structure_report import TextUnit
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


def _seed_openrecall_db(tmp_path: Path, *, rows: list[dict[str, object]]) -> tuple[Path, Path]:
    storage_dir = tmp_path / "openrecall"
    storage_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = storage_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
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
        for row in rows:
            timestamp = int(row["timestamp"])
            if row.get("with_screenshot", True):
                (screenshot_dir / f"{timestamp}.webp").write_bytes(b"fake-image")
            conn.execute(
                """
                INSERT INTO entries(app, title, text, timestamp, embedding)
                VALUES (?,?,?,?,?)
                """,
                (
                    str(row.get("app", "")),
                    str(row.get("title", "")),
                    str(row.get("text", "")),
                    timestamp,
                    row.get("embedding", b"embed"),
                ),
            )
        conn.commit()
    return source_db, storage_dir


def test_openrecall_import_normalizes_capture_rows_and_units(tmp_path: Path) -> None:
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(
        tmp_path,
        rows=[
            {
                "timestamp": source_ts,
                "app": "Firefox",
                "title": "Notification routing feature PR",
                "text": "Please implement the notification routing feature before Friday close of business.",
                "embedding": b"embed",
                "with_screenshot": True,
            }
        ],
    )
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
    source_db, storage_dir = _seed_openrecall_db(
        tmp_path,
        rows=[
            {
                "timestamp": source_ts,
                "app": "Firefox",
                "title": "Notification routing feature PR",
                "text": "Please implement the notification routing feature before Friday close of business.",
                "embedding": b"embed",
                "with_screenshot": True,
            }
        ],
    )
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
    source_db, storage_dir = _seed_openrecall_db(
        tmp_path,
        rows=[
            {
                "timestamp": source_ts,
                "app": "Firefox",
                "title": "Notification routing feature PR",
                "text": "Please implement the notification routing feature before Friday close of business.",
                "embedding": b"embed",
                "with_screenshot": True,
            }
        ],
    )
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


def test_openrecall_query_helpers_expose_runs_summary_and_filtered_captures(tmp_path: Path) -> None:
    first_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    second_ts = int(datetime(2026, 3, 9, 15, 5, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(
        tmp_path,
        rows=[
            {
                "timestamp": first_ts,
                "app": "Firefox",
                "title": "Notification routing feature PR",
                "text": "Please implement the notification routing feature before Friday close of business.",
                "embedding": b"embed",
                "with_screenshot": True,
            },
            {
                "timestamp": second_ts,
                "app": "Slack",
                "title": "Josh DM",
                "text": "Hey have you implemented the new feature yet?",
                "embedding": None,
                "with_screenshot": False,
            },
        ],
    )
    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-query-v1",
        )
        conn.commit()
        runs = load_openrecall_import_runs(conn, limit=5)
        assert len(runs) == 1
        assert runs[0]["importRunId"] == "openrecall-query-v1"
        assert runs[0]["screenshotCoverage"]["withScreenshot"] == 1
        summary = build_openrecall_capture_summary(conn)
        assert summary["captureCount"] == 2
        assert summary["screenshotCoverage"]["withScreenshot"] == 1
        assert summary["countsByApp"][0]["appName"] in {"Firefox", "Slack"}
        march_ninth = build_openrecall_capture_summary(conn, date="2026-03-10")
        assert march_ninth["captureCount"] == 1
        captures = query_openrecall_captures(conn, text_query="new feature", limit=5)
        assert len(captures) == 1
        assert captures[0]["appName"] == "Slack"
        assert captures[0]["hasScreenshot"] is False


def test_query_openrecall_import_cli_returns_json_read_models(tmp_path: Path) -> None:
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    source_db, storage_dir = _seed_openrecall_db(
        tmp_path,
        rows=[
            {
                "timestamp": source_ts,
                "app": "Firefox",
                "title": "Notification routing feature PR",
                "text": "Please implement the notification routing feature before Friday close of business.",
                "embedding": b"embed",
                "with_screenshot": True,
            }
        ],
    )
    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-cli-v1",
        )
        conn.commit()
    base_cmd = [
        sys.executable,
        "SensibLaw/scripts/query_openrecall_import.py",
        "--itir-db-path",
        str(itir_db),
    ]
    runs_payload = json.loads(
        subprocess.run(
            [*base_cmd, "runs", "--limit", "2"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert runs_payload["ok"] is True
    assert runs_payload["runs"][0]["importRunId"] == "openrecall-cli-v1"
    summary_payload = json.loads(
        subprocess.run(
            [*base_cmd, "summary", "--import-run-id", "openrecall-cli-v1"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert summary_payload["summary"]["captureCount"] == 1
    captures_payload = json.loads(
        subprocess.run(
            [*base_cmd, "captures", "--text-query", "notification routing", "--limit", "5"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert len(captures_payload["captures"]) == 1
    assert captures_payload["captures"][0]["appName"] == "Firefox"


def test_openrecall_raw_row_scaffold_preserves_source_row_fields(tmp_path: Path) -> None:
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    storage_dir = tmp_path / "openrecall"
    storage_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = storage_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    (screenshot_dir / f"{source_ts}.webp").write_bytes(b"fake-image")
    source_db = storage_dir / "recall.db"
    with sqlite3.connect(source_db) as conn:
        conn.execute(
            """
            CREATE TABLE entries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              app TEXT,
              title TEXT,
              text TEXT,
              captured_date TEXT,
              timestamp INTEGER UNIQUE,
              embedding BLOB,
              normalized_text TEXT,
              normalization_version TEXT,
              normalization_issues_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO entries(
              app, title, text, captured_date, timestamp, embedding,
              normalized_text, normalization_version, normalization_issues_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                "Firefox",
                "Notification routing feature PR",
                "Please implement the notification routing feature before Friday close of business.",
                "2026-03-08",
                source_ts,
                b"embed",
                "Please implement the notification routing feature before Friday close of business.",
                "openrecall.ocr_normalize.v1",
                '{"extra_text":0}',
            ),
        )
        conn.commit()

    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_raw_row_schema(conn)
        summary = import_openrecall_raw_rows(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-raw-v1",
        )
        conn.commit()
        assert summary.imported_row_count == 1
        runs = load_openrecall_raw_import_runs(conn, limit=5)
        assert runs[0]["importRunId"] == "openrecall-raw-v1"
        rows = query_openrecall_raw_rows(conn, import_run_id="openrecall-raw-v1", limit=5)
        assert len(rows) == 1
        assert rows[0]["capturedDate"] == "2026-03-08"
        assert rows[0]["normalizationVersion"] == "openrecall.ocr_normalize.v1"
        stored = conn.execute(
            """
            SELECT raw_text, normalized_text, source_row_json
            FROM openrecall_raw_entry_rows
            """
        ).fetchone()
        assert stored is not None
        assert "notification routing feature" in str(stored["raw_text"]).casefold()
        assert "notification routing feature" in str(stored["normalized_text"]).casefold()
        payload = json.loads(str(stored["source_row_json"]))
        assert payload["captured_date"] == "2026-03-08"
        assert payload["normalization_version"] == "openrecall.ocr_normalize.v1"
