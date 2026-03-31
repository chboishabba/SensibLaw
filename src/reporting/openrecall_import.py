from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING
from typing import Any

from src.reporting.source_loaders import find_timestamped_artifact_path, resolve_loader_path
from src.reporting.source_identity import build_openrecall_capture_id, format_local_iso_and_date_from_timestamp
from src.reporting.text_unit_builders import build_header_body_text

if TYPE_CHECKING:
    from src.reporting.structure_report import TextUnit


@dataclass(frozen=True, slots=True)
class OpenRecallImportSummary:
    import_run_id: str
    source_db_path: str
    source_entry_count: int
    imported_capture_count: int
    latest_source_timestamp: int | None


def _coverage_payload(with_screenshot: int, total: int) -> dict[str, Any]:
    without = max(int(total) - int(with_screenshot), 0)
    pct = 0.0
    if total > 0:
        pct = round((float(with_screenshot) / float(total)) * 100.0, 2)
    return {
        "withScreenshot": int(with_screenshot),
        "withoutScreenshot": without,
        "coveragePercent": pct,
    }


def ensure_openrecall_capture_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_import_runs (
          import_run_id TEXT PRIMARY KEY,
          source_db_path TEXT NOT NULL,
          storage_path TEXT,
          imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          source_entry_count INTEGER NOT NULL DEFAULT 0,
          imported_capture_count INTEGER NOT NULL DEFAULT 0,
          latest_source_timestamp INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_capture_sources (
          capture_id TEXT PRIMARY KEY,
          import_run_id TEXT NOT NULL REFERENCES openrecall_import_runs(import_run_id) ON DELETE CASCADE,
          source_db_path TEXT NOT NULL,
          source_entry_id INTEGER,
          source_timestamp INTEGER NOT NULL,
          captured_at TEXT NOT NULL,
          captured_date TEXT NOT NULL,
          app_name TEXT NOT NULL DEFAULT '',
          window_title TEXT NOT NULL DEFAULT '',
          ocr_text TEXT NOT NULL DEFAULT '',
          screenshot_path TEXT,
          screenshot_hash TEXT,
          embedding_present INTEGER NOT NULL DEFAULT 0,
          content_sha1 TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_db_path, source_timestamp)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_capture_text_units (
          unit_id TEXT PRIMARY KEY,
          capture_id TEXT NOT NULL REFERENCES openrecall_capture_sources(capture_id) ON DELETE CASCADE,
          unit_order INTEGER NOT NULL,
          text TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openrecall_capture_refs (
          capture_id TEXT NOT NULL REFERENCES openrecall_capture_sources(capture_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_kind TEXT NOT NULL,
          ref_value TEXT NOT NULL,
          PRIMARY KEY (capture_id, ref_order)
        )
        """
    )


def _screenshot_path_for_timestamp(*, source_db_path: Path, storage_path: Path | None, timestamp: int) -> Path | None:
    candidates: list[Path] = []
    if storage_path is not None:
        candidates.append(storage_path / "screenshots")
    candidates.append(source_db_path.parent / "screenshots")
    return find_timestamped_artifact_path(search_roots=candidates, timestamp=timestamp, suffix=".webp")


def _content_sha1(app_name: str, window_title: str, ocr_text: str) -> str:
    payload = f"{app_name}\n{window_title}\n{ocr_text}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _unit_text(app_name: str, window_title: str, ocr_text: str) -> str:
    parts = []
    if app_name.strip():
        parts.append(f"[{app_name.strip()}]")
    if window_title.strip():
        parts.append(window_title.strip())
    header = " ".join(parts).strip()
    return build_header_body_text(header=header, body=str(ocr_text or "").strip())


def import_openrecall_db(
    conn: sqlite3.Connection,
    *,
    source_db_path: str | Path,
    import_run_id: str,
    storage_path: str | Path | None = None,
    limit: int | None = None,
) -> OpenRecallImportSummary:
    ensure_openrecall_capture_schema(conn)
    resolved_source = resolve_loader_path(source_db_path)
    resolved_storage = resolve_loader_path(storage_path) if storage_path is not None else None
    with sqlite3.connect(str(resolved_source)) as src:
        src.row_factory = sqlite3.Row
        query = """
            SELECT id, app, title, text, timestamp, embedding
            FROM entries
            ORDER BY timestamp ASC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (int(limit),)
        rows = src.execute(query, params).fetchall()
    conn.execute(
        """
        INSERT INTO openrecall_import_runs(import_run_id, source_db_path, storage_path, imported_at, source_entry_count, imported_capture_count, latest_source_timestamp)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(import_run_id) DO UPDATE SET
          source_db_path=excluded.source_db_path,
          storage_path=excluded.storage_path,
          imported_at=excluded.imported_at,
          source_entry_count=excluded.source_entry_count,
          imported_capture_count=excluded.imported_capture_count,
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
        capture_id = build_openrecall_capture_id(source_db_path=str(resolved_source), source_timestamp=ts)
        captured_at, captured_date = format_local_iso_and_date_from_timestamp(ts)
        app_name = str(row["app"] or "")
        window_title = str(row["title"] or "")
        ocr_text = str(row["text"] or "")
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
        embedding_present = 1 if row["embedding"] is not None else 0
        content_sha1 = _content_sha1(app_name, window_title, ocr_text)
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO openrecall_capture_sources(
              capture_id, import_run_id, source_db_path, source_entry_id, source_timestamp,
              captured_at, captured_date, app_name, window_title, ocr_text,
              screenshot_path, screenshot_hash, embedding_present, content_sha1
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                capture_id,
                import_run_id,
                str(resolved_source),
                int(row["id"]) if row["id"] is not None else None,
                ts,
                captured_at,
                captured_date,
                app_name,
                window_title,
                ocr_text,
                str(screenshot_path) if screenshot_path is not None else None,
                screenshot_hash,
                embedding_present,
                content_sha1,
            ),
        )
        changed = conn.total_changes > before
        if changed:
            imported_count += 1
            conn.execute(
                """
                INSERT INTO openrecall_capture_text_units(unit_id, capture_id, unit_order, text)
                VALUES (?,?,?,?)
                """,
                (
                    f"{capture_id}:1",
                    capture_id,
                    1,
                    _unit_text(app_name, window_title, ocr_text),
                ),
            )
            ref_rows = [
                ("source_db_path", str(resolved_source)),
            ]
            if screenshot_path is not None:
                ref_rows.append(("screenshot_path", str(screenshot_path)))
            if window_title.strip():
                ref_rows.append(("window_title", window_title.strip()))
            if app_name.strip():
                ref_rows.append(("app_name", app_name.strip()))
            for ref_order, (ref_kind, ref_value) in enumerate(ref_rows):
                conn.execute(
                    """
                    INSERT INTO openrecall_capture_refs(capture_id, ref_order, ref_kind, ref_value)
                    VALUES (?,?,?,?)
                    """,
                    (capture_id, ref_order, ref_kind, ref_value),
                )
    conn.execute(
        """
        UPDATE openrecall_import_runs
        SET imported_capture_count = ?
        WHERE import_run_id = ?
        """,
        (imported_count, import_run_id),
    )
    return OpenRecallImportSummary(
        import_run_id=import_run_id,
        source_db_path=str(resolved_source),
        source_entry_count=len(rows),
        imported_capture_count=imported_count,
        latest_source_timestamp=max((int(row["timestamp"]) for row in rows), default=None),
    )


def load_openrecall_units(
    db_path: str | Path,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    limit: int | None = None,
) -> list["TextUnit"]:
    from src.reporting.structure_report import TextUnit  # noqa: PLC0415

    resolved = Path(db_path).expanduser().resolve()
    with sqlite3.connect(str(resolved)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_openrecall_capture_schema(conn)
        where: list[str] = []
        params: list[Any] = []
        if import_run_id is not None:
            where.append("s.import_run_id = ?")
            params.append(import_run_id)
        if date is not None:
            where.append("s.captured_date = ?")
            params.append(date)
        sql = """
            SELECT u.unit_id, u.capture_id, u.text
            FROM openrecall_capture_text_units u
            JOIN openrecall_capture_sources s ON s.capture_id = u.capture_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.source_timestamp ASC, u.unit_order ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [
            TextUnit(
                unit_id=str(row["unit_id"]),
                source_id=str(row["capture_id"]),
                source_type="openrecall_capture",
                text=str(row["text"]),
            )
            for row in rows
            if str(row["text"]).strip()
        ]


def load_openrecall_activity_rows(
    conn: sqlite3.Connection,
    *,
    date: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    ensure_openrecall_capture_schema(conn)
    sql = """
        SELECT capture_id, captured_at, app_name, window_title, ocr_text, screenshot_path, source_db_path
        FROM openrecall_capture_sources
        WHERE captured_date = ?
        ORDER BY source_timestamp ASC
    """
    params: list[Any] = [date]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        ts = str(row["captured_at"] or "")
        detail_parts = [part for part in [str(row["window_title"] or "").strip(), str(row["ocr_text"] or "").strip()] if part]
        detail = " — ".join(detail_parts[:2])[:240]
        hour = None
        try:
            hour = int(datetime.fromisoformat(ts).hour)
        except Exception:
            hour = None
        out.append(
            {
                "ts": ts,
                "hour": hour,
                "kind": "openrecall_capture",
                "detail": detail,
                "source_path": str(row["screenshot_path"] or row["source_db_path"] or ""),
                "meta": {
                    "captureId": str(row["capture_id"]),
                    "appName": str(row["app_name"] or ""),
                    "windowTitle": str(row["window_title"] or ""),
                    "sourceKind": "openrecall_capture",
                },
            }
        )
    return out


def load_openrecall_import_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ensure_openrecall_capture_schema(conn)
    rows = conn.execute(
        """
        SELECT
          r.import_run_id,
          r.source_db_path,
          r.storage_path,
          r.imported_at,
          r.source_entry_count,
          r.imported_capture_count,
          r.latest_source_timestamp,
          MIN(s.captured_at) AS first_captured_at,
          MAX(s.captured_at) AS last_captured_at,
          SUM(CASE WHEN s.screenshot_path IS NOT NULL AND TRIM(s.screenshot_path) <> '' THEN 1 ELSE 0 END) AS screenshot_count
        FROM openrecall_import_runs r
        LEFT JOIN openrecall_capture_sources s ON s.import_run_id = r.import_run_id
        GROUP BY r.import_run_id
        ORDER BY r.imported_at DESC, r.import_run_id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        imported = int(row["imported_capture_count"] or 0)
        screenshot_count = int(row["screenshot_count"] or 0)
        out.append(
            {
                "importRunId": str(row["import_run_id"]),
                "sourceDbPath": str(row["source_db_path"] or ""),
                "storagePath": str(row["storage_path"] or ""),
                "importedAt": str(row["imported_at"] or ""),
                "sourceEntryCount": int(row["source_entry_count"] or 0),
                "importedCaptureCount": imported,
                "latestSourceTimestamp": row["latest_source_timestamp"],
                "firstCapturedAt": row["first_captured_at"],
                "lastCapturedAt": row["last_captured_at"],
                "screenshotCoverage": _coverage_payload(screenshot_count, imported),
            }
        )
    return out


def build_openrecall_capture_summary(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    app_name: str | None = None,
) -> dict[str, Any]:
    ensure_openrecall_capture_schema(conn)
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
    where_sql = ""
    if where:
        where_sql = " WHERE " + " AND ".join(where)
    totals = conn.execute(
        f"""
        SELECT
          COUNT(*) AS capture_count,
          MIN(captured_at) AS first_captured_at,
          MAX(captured_at) AS last_captured_at,
          SUM(CASE WHEN screenshot_path IS NOT NULL AND TRIM(screenshot_path) <> '' THEN 1 ELSE 0 END) AS screenshot_count
        FROM openrecall_capture_sources
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int((totals["capture_count"] if totals is not None else 0) or 0)
    screenshot_count = int((totals["screenshot_count"] if totals is not None else 0) or 0)
    app_rows = conn.execute(
        f"""
        SELECT app_name, COUNT(*) AS capture_count
        FROM openrecall_capture_sources
        {where_sql}
        GROUP BY app_name
        ORDER BY capture_count DESC, app_name ASC
        LIMIT 10
        """,
        tuple(params),
    ).fetchall()
    title_rows = conn.execute(
        f"""
        SELECT window_title, COUNT(*) AS capture_count
        FROM openrecall_capture_sources
        {where_sql}
        GROUP BY window_title
        ORDER BY capture_count DESC, window_title ASC
        LIMIT 10
        """,
        tuple(params),
    ).fetchall()
    date_rows = conn.execute(
        f"""
        SELECT captured_date, COUNT(*) AS capture_count
        FROM openrecall_capture_sources
        {where_sql}
        GROUP BY captured_date
        ORDER BY captured_date DESC
        LIMIT 14
        """,
        tuple(params),
    ).fetchall()
    return {
        "filters": {
            "importRunId": import_run_id,
            "date": date,
            "appName": app_name,
        },
        "captureCount": total,
        "firstCapturedAt": totals["first_captured_at"] if totals is not None else None,
        "lastCapturedAt": totals["last_captured_at"] if totals is not None else None,
        "screenshotCoverage": _coverage_payload(screenshot_count, total),
        "countsByApp": [
            {
                "appName": str(row["app_name"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in app_rows
        ],
        "countsByTitle": [
            {
                "windowTitle": str(row["window_title"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in title_rows
        ],
        "countsByDate": [
            {
                "capturedDate": str(row["captured_date"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in date_rows
        ],
    }


def query_openrecall_captures(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    app_name: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    ensure_openrecall_capture_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    if import_run_id is not None:
        where.append("s.import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("s.captured_date = ?")
        params.append(date)
    if app_name is not None:
        where.append("LOWER(s.app_name) = LOWER(?)")
        params.append(app_name)
    if text_query is not None and text_query.strip():
        needle = f"%{text_query.strip().casefold()}%"
        where.append(
            "(LOWER(s.ocr_text) LIKE ? OR LOWER(s.window_title) LIKE ? OR LOWER(s.app_name) LIKE ?)"
        )
        params.extend([needle, needle, needle])
    sql = """
        SELECT
          s.capture_id,
          s.import_run_id,
          s.captured_at,
          s.captured_date,
          s.app_name,
          s.window_title,
          s.ocr_text,
          s.screenshot_path,
          s.source_db_path,
          s.embedding_present
        FROM openrecall_capture_sources s
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.source_timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        app = str(row["app_name"] or "").strip()
        title = str(row["window_title"] or "").strip()
        ocr = str(row["ocr_text"] or "").strip()
        preview_parts = [part for part in [title, ocr] if part]
        out.append(
            {
                "captureId": str(row["capture_id"]),
                "importRunId": str(row["import_run_id"]),
                "capturedAt": str(row["captured_at"] or ""),
                "capturedDate": str(row["captured_date"] or ""),
                "appName": app,
                "windowTitle": title,
                "ocrPreview": " — ".join(preview_parts[:2])[:240],
                "hasScreenshot": bool(str(row["screenshot_path"] or "").strip()),
                "screenshotPath": str(row["screenshot_path"] or ""),
                "sourceDbPath": str(row["source_db_path"] or ""),
                "embeddingPresent": bool(int(row["embedding_present"] or 0)),
            }
        )
    return out
