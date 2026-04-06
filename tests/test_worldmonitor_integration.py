from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from src.reporting.worldmonitor_import import (
    ensure_worldmonitor_capture_schema,
    import_worldmonitor_data,
    load_worldmonitor_import_runs,
    load_worldmonitor_units,
    build_worldmonitor_capture_summary,
    query_worldmonitor_captures,
    load_worldmonitor_activity_rows,
)


def test_worldmonitor_import_normalizes_fixtures_to_units_and_queries(tmp_path: Path) -> None:
    source_dir = tmp_path / "worldmonitor"
    source_dir.mkdir(parents=True, exist_ok=True)

    (source_dir / "gamma-irradiators.json").write_text(
        json.dumps(
            {
                "source": "sample-source",
                "url": "https://example.org",
                "extracted": "2026-03-08",
                "cities": ["Vega Alta", "Qormi"],
                "countries": ["Puerto Rico"],
                "organizations": ["Lab A"],
                "realValues": [{"value": 12}, {"value": 99}],
                "note": "sample row",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_worldmonitor_capture_schema(conn)
        summary = import_worldmonitor_data(
            conn,
            source_path=source_dir,
            import_run_id="worldmonitor-test-v1",
            limit=None,
        )
        conn.commit()

        assert summary.source_file_count == 1
        assert summary.source_record_count == 7
        assert summary.imported_capture_count == 7

        runs = load_worldmonitor_import_runs(conn, limit=5)
        assert len(runs) == 1
        assert runs[0]["importRunId"] == "worldmonitor-test-v1"
        assert runs[0]["sourceRecordCount"] == 7

        summary_payload = build_worldmonitor_capture_summary(conn, import_run_id="worldmonitor-test-v1")
        assert summary_payload["captureCount"] == 7
        assert summary_payload["labelCoverage"]["withText"] == 7

        captures = query_worldmonitor_captures(conn, import_run_id="worldmonitor-test-v1", limit=10)
        assert captures
        assert captures[0]["importRunId"] == "worldmonitor-test-v1"
        assert captures[0]["sourceFile"] == str(source_dir / "gamma-irradiators.json")

        rows = load_worldmonitor_activity_rows(conn, date=captures[0]["capturedDate"], limit=10)
        assert rows
        assert any(row["kind"] == "worldmonitor_capture" for row in rows)

    units = load_worldmonitor_units(itir_db, import_run_id="worldmonitor-test-v1", limit=3)
    assert len(units) == 3
    assert units[0].source_type == "worldmonitor_capture"
    assert units[0].text.strip()
