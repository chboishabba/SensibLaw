from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from src.reporting.structure_report import TextUnit


@dataclass(frozen=True, slots=True)
class OpenRecallImportSummary:
    import_run_id: str
    source_db_path: str
    source_entry_count: int
    imported_capture_count: int
    latest_source_timestamp: int | None


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


def _capture_id(source_db_path: str, source_timestamp: int) -> str:
    digest = hashlib.sha1(f"{source_db_path}|{source_timestamp}".encode("utf-8")).hexdigest()[:16]
    return f"openrecall:{digest}"


def _iso_and_date_from_timestamp(ts: int) -> tuple[str, str]:
    local_dt = datetime.fromtimestamp(int(ts)).astimezone()
    return local_dt.isoformat(timespec="seconds"), local_dt.date().isoformat()


def _screenshot_path_for_timestamp(*, source_db_path: Path, storage_path: Path | None, timestamp: int) -> Path | None:
    candidates: list[Path] = []
    if storage_path is not None:
        candidates.append(storage_path / "screenshots")
    candidates.append(source_db_path.parent / "screenshots")
    for root in candidates:
        if not root.exists():
            continue
        exact = sorted(root.glob(f"{timestamp}.webp"))
        if exact:
            return exact[0]
        indexed = sorted(root.glob(f"{timestamp}_*.webp"))
        if indexed:
            return indexed[0]
    return None


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
    body = str(ocr_text or "").strip()
    if header and body:
        return f"{header}\n{body}"
    return header or body


def import_openrecall_db(
    conn: sqlite3.Connection,
    *,
    source_db_path: str | Path,
    import_run_id: str,
    storage_path: str | Path | None = None,
    limit: int | None = None,
) -> OpenRecallImportSummary:
    ensure_openrecall_capture_schema(conn)
    resolved_source = Path(source_db_path).expanduser().resolve()
    resolved_storage = Path(storage_path).expanduser().resolve() if storage_path is not None else None
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
        capture_id = _capture_id(str(resolved_source), ts)
        captured_at, captured_date = _iso_and_date_from_timestamp(ts)
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
