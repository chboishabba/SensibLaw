from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.reporting.openrecall_import import load_openrecall_source_rows
from src.reporting.source_identity import format_local_iso_and_date_from_timestamp
from src.reporting.source_loaders import find_timestamped_artifact_path, resolve_loader_path


@dataclass(frozen=True, slots=True)
class OpenRecallRawImportSummary:
    import_run_id: str
    source_db_path: str
    source_entry_count: int
    imported_row_count: int
    latest_source_timestamp: int | None


def ensure_openrecall_raw_row_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_raw_import_runs (
          import_run_id TEXT PRIMARY KEY,
          source_db_path TEXT NOT NULL,
          storage_path TEXT,
          imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          source_entry_count INTEGER NOT NULL DEFAULT 0,
          imported_row_count INTEGER NOT NULL DEFAULT 0,
          latest_source_timestamp INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_raw_entry_rows (
          raw_row_id TEXT PRIMARY KEY,
          import_run_id TEXT NOT NULL REFERENCES openrecall_raw_import_runs(import_run_id) ON DELETE CASCADE,
          source_db_path TEXT NOT NULL,
          source_entry_id INTEGER,
          source_timestamp INTEGER NOT NULL,
          captured_at TEXT NOT NULL,
          captured_date TEXT NOT NULL,
          app_name TEXT NOT NULL DEFAULT '',
          window_title TEXT NOT NULL DEFAULT '',
          raw_text TEXT NOT NULL DEFAULT '',
          normalized_text TEXT,
          normalization_version TEXT,
          normalization_issues_json TEXT,
          screenshot_path TEXT,
          screenshot_hash TEXT,
          embedding_present INTEGER NOT NULL DEFAULT 0,
          source_row_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_db_path, source_timestamp)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_openrecall_raw_row_day_time
        ON openrecall_raw_entry_rows (captured_date, source_timestamp)
        """
    )


def _raw_row_id(*, source_db_path: str, source_timestamp: int) -> str:
    digest = hashlib.sha1(
        f"{source_db_path}\n{int(source_timestamp)}\nopenrecall_raw_row".encode("utf-8")
    ).hexdigest()
    return f"openrecall_raw_row:{digest}"


def _screenshot_path_for_timestamp(
    *,
    source_db_path: Path,
    storage_path: Path | None,
    timestamp: int,
) -> Path | None:
    candidates: list[Path] = []
    if storage_path is not None:
        candidates.append(storage_path / "screenshots")
    candidates.append(source_db_path.parent / "screenshots")
    return find_timestamped_artifact_path(
        search_roots=candidates,
        timestamp=timestamp,
        suffix=".webp",
    )


def import_openrecall_raw_rows(
    conn: sqlite3.Connection,
    *,
    source_db_path: str | Path,
    import_run_id: str,
    storage_path: str | Path | None = None,
    limit: int | None = None,
) -> OpenRecallRawImportSummary:
    ensure_openrecall_raw_row_schema(conn)
    resolved_source, rows = load_openrecall_source_rows(source_db_path, limit=limit)
    resolved_storage = (
        resolve_loader_path(storage_path) if storage_path is not None else None
    )
    conn.execute(
        """
        INSERT INTO openrecall_raw_import_runs(
          import_run_id, source_db_path, storage_path, imported_at,
          source_entry_count, imported_row_count, latest_source_timestamp
        ) VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(import_run_id) DO UPDATE SET
          source_db_path=excluded.source_db_path,
          storage_path=excluded.storage_path,
          imported_at=excluded.imported_at,
          source_entry_count=excluded.source_entry_count,
          imported_row_count=excluded.imported_row_count,
          latest_source_timestamp=excluded.latest_source_timestamp
        """,
        (
            import_run_id,
            str(resolved_source),
            str(resolved_storage) if resolved_storage is not None else None,
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            len(rows),
            0,
            max((int(row["timestamp"]) for row in rows), default=None),
        ),
    )
    imported_count = 0
    for row in rows:
        ts = int(row["timestamp"])
        captured_at, fallback_captured_date = format_local_iso_and_date_from_timestamp(ts)
        captured_date = (
            str(row["captured_date"] or fallback_captured_date)
            if "captured_date" in row.keys()
            else fallback_captured_date
        )
        screenshot_path = _screenshot_path_for_timestamp(
            source_db_path=resolved_source,
            storage_path=resolved_storage,
            timestamp=ts,
        )
        screenshot_hash = (
            hashlib.sha1(screenshot_path.read_bytes()).hexdigest()
            if screenshot_path is not None and screenshot_path.exists()
            else None
        )
        source_row_json = json.dumps(
            {key: row[key] for key in row.keys()},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO openrecall_raw_entry_rows(
              raw_row_id, import_run_id, source_db_path, source_entry_id, source_timestamp,
              captured_at, captured_date, app_name, window_title, raw_text,
              normalized_text, normalization_version, normalization_issues_json,
              screenshot_path, screenshot_hash, embedding_present, source_row_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                _raw_row_id(source_db_path=str(resolved_source), source_timestamp=ts),
                import_run_id,
                str(resolved_source),
                int(row["id"]) if row["id"] is not None else None,
                ts,
                captured_at,
                captured_date,
                str(row["app"] or ""),
                str(row["title"] or ""),
                str(row["text"] or ""),
                str(row["normalized_text"] or "") if "normalized_text" in row.keys() else None,
                str(row["normalization_version"] or "") if "normalization_version" in row.keys() else None,
                str(row["normalization_issues_json"] or "") if "normalization_issues_json" in row.keys() else None,
                str(screenshot_path) if screenshot_path is not None else None,
                screenshot_hash,
                1 if row["embedding"] is not None else 0,
                source_row_json,
            ),
        )
        if conn.total_changes > before:
            imported_count += 1
    conn.execute(
        """
        UPDATE openrecall_raw_import_runs
        SET imported_row_count = ?
        WHERE import_run_id = ?
        """,
        (imported_count, import_run_id),
    )
    return OpenRecallRawImportSummary(
        import_run_id=import_run_id,
        source_db_path=str(resolved_source),
        source_entry_count=len(rows),
        imported_row_count=imported_count,
        latest_source_timestamp=max((int(row["timestamp"]) for row in rows), default=None),
    )


def load_openrecall_raw_import_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ensure_openrecall_raw_row_schema(conn)
    rows = conn.execute(
        """
        SELECT import_run_id, source_db_path, storage_path, imported_at,
               source_entry_count, imported_row_count, latest_source_timestamp
        FROM openrecall_raw_import_runs
        ORDER BY imported_at DESC, import_run_id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [
        {
            "importRunId": str(row["import_run_id"]),
            "sourceDbPath": str(row["source_db_path"]),
            "storagePath": str(row["storage_path"] or ""),
            "importedAt": str(row["imported_at"] or ""),
            "sourceEntryCount": int(row["source_entry_count"] or 0),
            "importedRowCount": int(row["imported_row_count"] or 0),
            "latestSourceTimestamp": row["latest_source_timestamp"],
        }
        for row in rows
    ]


def query_openrecall_raw_rows(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    app_name: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    ensure_openrecall_raw_row_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    if import_run_id is not None:
        where.append("import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("captured_date = ?")
        params.append(date)
    if app_name is not None:
        where.append("LOWER(app_name) = LOWER(?)")
        params.append(app_name)
    if text_query is not None and text_query.strip():
        needle = f"%{text_query.strip().casefold()}%"
        where.append(
            "(LOWER(raw_text) LIKE ? OR LOWER(window_title) LIKE ? OR LOWER(app_name) LIKE ?)"
        )
        params.extend([needle, needle, needle])
    sql = """
        SELECT raw_row_id, import_run_id, source_db_path, source_entry_id,
               source_timestamp, captured_at, captured_date, app_name, window_title,
               raw_text, normalized_text, normalization_version,
               normalization_issues_json, screenshot_path, embedding_present
        FROM openrecall_raw_entry_rows
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY source_timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [
        {
            "rawRowId": str(row["raw_row_id"]),
            "importRunId": str(row["import_run_id"]),
            "sourceDbPath": str(row["source_db_path"] or ""),
            "sourceEntryId": row["source_entry_id"],
            "sourceTimestamp": int(row["source_timestamp"]),
            "capturedAt": str(row["captured_at"] or ""),
            "capturedDate": str(row["captured_date"] or ""),
            "appName": str(row["app_name"] or ""),
            "windowTitle": str(row["window_title"] or ""),
            "rawTextPreview": str(row["raw_text"] or "")[:240],
            "normalizedTextPreview": str(row["normalized_text"] or "")[:240],
            "normalizationVersion": str(row["normalization_version"] or ""),
            "normalizationIssues": (
                json.loads(str(row["normalization_issues_json"]))
                if str(row["normalization_issues_json"] or "").strip()
                else None
            ),
            "hasScreenshot": bool(str(row["screenshot_path"] or "").strip()),
            "embeddingPresent": bool(int(row["embedding_present"] or 0)),
        }
        for row in rows
    ]


__all__ = [
    "OpenRecallRawImportSummary",
    "ensure_openrecall_raw_row_schema",
    "import_openrecall_raw_rows",
    "load_openrecall_raw_import_runs",
    "query_openrecall_raw_rows",
]
