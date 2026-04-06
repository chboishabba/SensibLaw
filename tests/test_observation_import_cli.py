from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from src.reporting.observation_lanes import (
    load_observation_import_runs,
    load_observation_units,
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
            ("Firefox", "Import CLI check", text, timestamp, b"embed"),
        )
        conn.commit()
    return db_path, storage_dir


def _seed_worldmonitor_dir(tmp_path: Path) -> Path:
    source_dir = tmp_path / "worldmonitor"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "sample.json").write_text(
        """
{"source": "sample-source", "url": "https://example.org", "extracted": "2026-03-08", "cities": ["Sample"], "note": "cli test"}
""".strip(),
        encoding="utf-8",
    )
    return source_dir


def _run_script(cmd: list[str], cwd: Path) -> dict[str, object]:
    return json.loads(
        subprocess.run(
            [*cmd],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def test_import_observation_cli_openrecall_roundtrip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ts = int(datetime(2026, 3, 8, 11, 0, tzinfo=timezone.utc).timestamp())
    source_db, storage = _seed_openrecall_db(tmp_path, timestamp=ts, text="observer import route")
    itir_db = tmp_path / "itir.sqlite"

    payload = _run_script(
        [
            sys.executable,
            "SensibLaw/scripts/import_observation.py",
            "--lane",
            "openrecall",
            "--source-path",
            str(source_db),
            "--storage-path",
            str(storage),
            "--import-run-id",
            "observation-openrecall-cli-v1",
            "--itir-db-path",
            str(itir_db),
            "--show-units",
        ],
        cwd=repo_root,
    )
    assert payload["ok"] is True
    assert payload["lane"] == "openrecall"
    assert payload["importRunId"] == "observation-openrecall-cli-v1"
    assert payload["importedCaptureCount"] == 1
    assert payload["sourceDbPath"].endswith("recall.db")
    assert payload["unitPreview"]

    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        runs = load_observation_import_runs(conn, "openrecall", limit=5)
        assert runs[0]["importRunId"] == "observation-openrecall-cli-v1"
    units = load_observation_units(itir_db, "openrecall", import_run_id="observation-openrecall-cli-v1")
    assert len(units) == 1


def test_import_observation_cli_worldmonitor_and_query_roundtrip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_dir = _seed_worldmonitor_dir(tmp_path)
    itir_db = tmp_path / "itir.sqlite"

    payload = _run_script(
        [
            sys.executable,
            "SensibLaw/scripts/import_observation.py",
            "--lane",
            "worldmonitor",
            "--source-path",
            str(source_dir),
            "--import-run-id",
            "observation-worldmonitor-cli-v1",
            "--itir-db-path",
            str(itir_db),
        ],
        cwd=repo_root,
    )
    assert payload["ok"] is True
    assert payload["lane"] == "worldmonitor"
    assert payload["importRunId"] == "observation-worldmonitor-cli-v1"
    assert payload["importedCaptureCount"] == payload["sourceRecordCount"]
    assert payload["importedCaptureCount"] > 0

    summary_payload = _run_script(
        [
            sys.executable,
            "SensibLaw/scripts/query_observation_import.py",
            "--lane",
            "worldmonitor",
            "--itir-db-path",
            str(itir_db),
            "summary",
            "--import-run-id",
            "observation-worldmonitor-cli-v1",
        ],
        cwd=repo_root,
    )
    assert summary_payload["lane"] == "worldmonitor"
    assert summary_payload["summary"]["captureCount"] == payload["importedCaptureCount"]
