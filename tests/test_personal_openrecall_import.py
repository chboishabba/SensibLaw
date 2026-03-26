from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from scripts.build_personal_handoff_from_openrecall import build_handoff_from_openrecall_artifact, main
from src.reporting.openrecall_import import ensure_openrecall_capture_schema, import_openrecall_db


def _seed_openrecall_db(tmp_path: Path) -> tuple[Path, Path]:
    storage_dir = tmp_path / "openrecall"
    storage_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = storage_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    source_db = storage_dir / "recall.db"
    source_ts = int(datetime(2026, 3, 8, 10, 15, tzinfo=timezone.utc).timestamp())
    (screenshot_dir / f"{source_ts}.webp").write_bytes(b"fake-image")
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
                source_ts,
                b"embed",
            ),
        )
        conn.commit()
    return source_db, storage_dir


def _make_itir_with_openrecall(tmp_path: Path) -> Path:
    source_db, storage_dir = _seed_openrecall_db(tmp_path)
    itir_db = tmp_path / "itir.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        import_openrecall_db(
            conn,
            source_db_path=source_db,
            storage_path=storage_dir,
            import_run_id="openrecall-handoff-v1",
        )
        conn.commit()
    return itir_db


def test_openrecall_import_builds_personal_handoff(tmp_path: Path) -> None:
    itir_db = _make_itir_with_openrecall(tmp_path)

    payload = build_handoff_from_openrecall_artifact(
        itir_db_path=itir_db,
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:openrecall_handoff",
        mode="personal_handoff",
        import_run_id="openrecall-handoff-v1",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert normalized["entries"][0]["source_type"] == "openrecall_capture"
    assert "[Firefox]" in normalized["entries"][0]["text"]
    assert report["recipient_export"]["exported_item_count"] == 1


def test_openrecall_import_builds_protected_envelope_without_raw_text(tmp_path: Path) -> None:
    itir_db = _make_itir_with_openrecall(tmp_path)

    payload = build_handoff_from_openrecall_artifact(
        itir_db_path=itir_db,
        output_dir=tmp_path / "artifact",
        recipient_profile="lawyer",
        source_label="fixture:openrecall_protected",
        mode="protected_disclosure_envelope",
        import_run_id="openrecall-handoff-v1",
    )

    normalized = json.loads(Path(payload["normalized_input_path"]).read_text(encoding="utf-8"))
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    serialized = json.dumps(report, sort_keys=True)
    assert normalized["entries"][0]["local_handle"].startswith("openrecall_capture://")
    assert report["integrity"]["sealed_item_count"] == 1
    assert "Please implement the notification routing feature" not in serialized


def test_openrecall_import_script_writes_artifact(tmp_path: Path, capsys) -> None:
    itir_db = _make_itir_with_openrecall(tmp_path)

    exit_code = main(
        [
            "--itir-db-path",
            str(itir_db),
            "--recipient-profile",
            "lawyer",
            "--source-label",
            "fixture:openrecall_handoff",
            "--import-run-id",
            "openrecall-handoff-v1",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert Path(payload["report_path"]).exists()
