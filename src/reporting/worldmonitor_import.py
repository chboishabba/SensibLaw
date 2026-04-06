from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import json
from typing import TYPE_CHECKING
from typing import Any

from src.reporting.source_loaders import resolve_loader_path
from src.reporting.source_identity import build_worldmonitor_capture_id, format_local_iso_and_date_from_timestamp
from src.reporting.text_unit_builders import build_header_body_text
from src.reporting.observation_lanes import ObservationLaneAdapter
from src.fact_intake.review_bundle import build_event_chronology

if TYPE_CHECKING:
    from src.reporting.structure_report import TextUnit


@dataclass(frozen=True, slots=True)
class WorldMonitorImportSummary:
    import_run_id: str
    source_path: str
    source_file_count: int
    source_record_count: int
    imported_capture_count: int
    latest_source_timestamp: int | None


def _format_payload_text(row: Any) -> str:
    if isinstance(row, dict):
        parts = [f"{key}: {row[key]}" for key in sorted(row.keys()) if row[key] is not None and row[key] != ""]
        if parts:
            return " | ".join(parts)
    text = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return str(text or "")


def _coverage_payload(with_row: int, total: int) -> dict[str, Any]:
    without = max(int(total) - int(with_row), 0)
    pct = 0.0
    if total > 0:
        pct = round((float(with_row) / float(total)) * 100.0, 2)
    return {
        "withText": int(with_row),
        "withoutText": without,
        "coveragePercent": pct,
    }


def ensure_worldmonitor_capture_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worldmonitor_import_runs (
          import_run_id TEXT PRIMARY KEY,
          source_path TEXT NOT NULL,
          imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          source_file_count INTEGER NOT NULL DEFAULT 0,
          source_record_count INTEGER NOT NULL DEFAULT 0,
          imported_capture_count INTEGER NOT NULL DEFAULT 0,
          latest_source_timestamp INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worldmonitor_capture_sources (
          capture_id TEXT PRIMARY KEY,
          import_run_id TEXT NOT NULL REFERENCES worldmonitor_import_runs(import_run_id) ON DELETE CASCADE,
          source_path TEXT NOT NULL,
          source_file TEXT NOT NULL,
          source_row_id TEXT NOT NULL,
          source_timestamp INTEGER NOT NULL,
          captured_at TEXT NOT NULL,
          captured_date TEXT NOT NULL,
          source_kind TEXT NOT NULL DEFAULT '',
          row_label TEXT NOT NULL DEFAULT '',
          content_sha1 TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_path, source_file, source_row_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worldmonitor_capture_text_units (
          unit_id TEXT PRIMARY KEY,
          capture_id TEXT NOT NULL REFERENCES worldmonitor_capture_sources(capture_id) ON DELETE CASCADE,
          unit_order INTEGER NOT NULL,
          text TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worldmonitor_capture_refs (
          capture_id TEXT NOT NULL REFERENCES worldmonitor_capture_sources(capture_id) ON DELETE CASCADE,
          ref_order INTEGER NOT NULL,
          ref_kind TEXT NOT NULL,
          ref_value TEXT NOT NULL,
          PRIMARY KEY (capture_id, ref_order)
        )
        """
    )


def _parse_extracted_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return int(value)
    candidate = str(value).strip()
    if not candidate:
        return None

    # Numeric string or seconds float
    try:
        parsed = float(candidate)
        if parsed > 0:
            return int(parsed)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(candidate, fmt)
            return int(dt.replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue

    try:
        return int(datetime.fromisoformat(candidate).timestamp())
    except ValueError:
        return None


def _stable_fallback_timestamp(raw: str, index: int) -> int:
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    bounded_seed = int(digest[:12], 16) % 365 * 24 * 60 * 60
    return 1_700_000_000 + bounded_seed + int(index)


def _to_row_text(row: dict[str, Any], *, source_row_id: str, source_kind: str) -> str:
    body = _format_payload_text(row)
    label = str(source_row_id or "") or str(row.get("id") or row.get("label") or source_kind)
    return build_header_body_text(header=f"{source_kind}: {label}", body=body)


def _build_rows_from_record(
    payload: dict[str, Any],
    *,
    source_file: str,
    source_extracted_ts: int | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if "facilities" in payload and isinstance(payload["facilities"], list):
        facilities = payload["facilities"]
        for index, row in enumerate(facilities):
            if not isinstance(row, dict):
                continue
            source_row_id = str(row.get("id") or f"facility:{index:04d}").strip()
            records.append(
                {
                    "source_file": source_file,
                    "source_row_id": source_row_id,
                    "source_kind": "facility",
                    "row_label": str(row.get("id") or row.get("city") or source_row_id),
                    "source_timestamp": source_extracted_ts + index if source_extracted_ts is not None else _stable_fallback_timestamp(
                        f"{source_file}|facility|{source_row_id}",
                        index,
                    ),
                    "payload": row,
                }
            )
        return records

    base = {
        key: value
        for key, value in payload.items()
        if key not in {"facilities"} and value is not None
    }

    if isinstance(base, dict) and base:
        metadata = {"source": base.get("source", ""), "url": base.get("url", ""), "extracted": base.get("extracted", "")}
        metadata.update(
            {
                "cities_count": len(base.get("cities", [])) if isinstance(base.get("cities"), list) else None,
                "countries_count": len(base.get("countries", [])) if isinstance(base.get("countries"), list) else None,
                "organizations_count": len(base.get("organizations", [])) if isinstance(base.get("organizations"), list) else None,
                "real_values_count": len(base.get("realValues", [])) if isinstance(base.get("realValues"), list) else None,
            }
        )
        records.append(
            {
                "source_file": source_file,
                "source_row_id": "metadata",
                "source_kind": "metadata",
                "row_label": "metadata",
                "source_timestamp": source_extracted_ts or _stable_fallback_timestamp(source_file, 0),
                "payload": metadata,
            }
        )

        for key in ("cities", "countries", "organizations", "realValues"):
            values = base.get(key)
            if not isinstance(values, list):
                continue
            for index, value in enumerate(values[:10]):
                if isinstance(value, (dict, list)):
                    payload_row = {"value": value}
                else:
                    payload_row = {key: str(value), "index": index}
                records.append(
                    {
                        "source_file": source_file,
                        "source_row_id": f"{key}:{index:04d}",
                        "source_kind": key,
                        "row_label": f"{key}:{index}",
                        "source_timestamp": (source_extracted_ts + index + 1)
                        if source_extracted_ts is not None
                        else _stable_fallback_timestamp(f"{source_file}|{key}|{index}", index),
                        "payload": payload_row,
                    }
                )

    return records


def _source_path_rows(source_path: Path, *, limit: int | None = None) -> list[Path]:
    if source_path.is_file():
        return [source_path]
    if source_path.is_dir():
        paths = sorted(path for path in source_path.rglob("*.json") if path.is_file())
        return paths if limit is None else paths[: limit]
    raise FileNotFoundError(str(source_path))


def import_worldmonitor_data(
    conn: sqlite3.Connection,
    *,
    source_path: str | Path,
    import_run_id: str,
    limit: int | None = None,
) -> WorldMonitorImportSummary:
    ensure_worldmonitor_capture_schema(conn)
    resolved_source = resolve_loader_path(source_path)
    source_rows = _source_path_rows(resolved_source, limit=limit)
    rows: list[dict[str, Any]] = []

    for source_file_path in source_rows:
        with source_file_path.open("r", encoding="utf-8") as source_file:
            payload = json.load(source_file)
        if not isinstance(payload, dict):
            continue

        extracted_ts = _parse_extracted_timestamp(payload.get("extracted"))
        records = _build_rows_from_record(
            payload,
            source_file=str(source_file_path),
            source_extracted_ts=extracted_ts,
        )
        for record in records:
            row_payload = record.get("payload")
            payload_text = row_payload
            if isinstance(row_payload, dict | list | str | int | float | bool):
                payload_text = row_payload
            elif row_payload is not None:
                payload_text = str(row_payload)
            else:
                payload_text = {}
            rows.append(
                {
                    **record,
                    "payload": payload_text,
                    "source_path": str(resolved_source),
                    "payload_sha1": hashlib.sha1(
                        json.dumps(payload_text, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest()[:20],
                }
            )

    conn.execute(
        """
        INSERT INTO worldmonitor_import_runs(
          import_run_id,
          source_path,
          imported_at,
          source_file_count,
          source_record_count,
          imported_capture_count,
          latest_source_timestamp
        )
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(import_run_id) DO UPDATE SET
          source_path=excluded.source_path,
          imported_at=excluded.imported_at,
          source_file_count=excluded.source_file_count,
          source_record_count=excluded.source_record_count,
          imported_capture_count=excluded.imported_capture_count,
          latest_source_timestamp=excluded.latest_source_timestamp
        """,
        (
            import_run_id,
            str(resolved_source),
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            len(source_rows),
            len(rows),
            0,
            max((int(item["source_timestamp"]) for item in rows), default=None),
        ),
    )
    imported_count = 0
    for item in rows:
        source_timestamp = int(item["source_timestamp"])
        captured_at, captured_date = format_local_iso_and_date_from_timestamp(source_timestamp)
        capture_id = build_worldmonitor_capture_id(
            source_path=str(item["source_path"]),
            source_file=str(item["source_file"]),
            source_row_id=str(item["source_row_id"]),
        )
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO worldmonitor_capture_sources(
              capture_id,
              import_run_id,
              source_path,
              source_file,
              source_row_id,
              source_timestamp,
              captured_at,
              captured_date,
              source_kind,
              row_label,
              content_sha1
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                capture_id,
                import_run_id,
                item["source_path"],
                item["source_file"],
                str(item["source_row_id"]),
                source_timestamp,
                captured_at,
                captured_date,
                str(item["source_kind"]),
                str(item["row_label"]),
                item["payload_sha1"],
            ),
        )
        changed = conn.total_changes > before
        if changed:
            imported_count += 1
            conn.execute(
                """
                INSERT INTO worldmonitor_capture_text_units(unit_id, capture_id, unit_order, text)
                VALUES (?,?,?,?)
                """,
                (
                    f"{capture_id}:1",
                    capture_id,
                    1,
                    _to_row_text(item["payload"], source_row_id=str(item["source_row_id"]), source_kind=str(item["source_kind"])),
                ),
            )
            ref_rows = [("source_path", item["source_path"]), ("source_file", item["source_file"])]
            if str(item.get("row_label") or "").strip():
                ref_rows.append(("row_label", str(item["row_label"])))
            for ref_order, (ref_kind, ref_value) in enumerate(ref_rows):
                conn.execute(
                    """
                    INSERT INTO worldmonitor_capture_refs(capture_id, ref_order, ref_kind, ref_value)
                    VALUES (?,?,?,?)
                    """,
                    (capture_id, ref_order, ref_kind, str(ref_value)),
                )

    conn.execute(
        """
        UPDATE worldmonitor_import_runs
        SET imported_capture_count = ?
        WHERE import_run_id = ?
        """,
        (imported_count, import_run_id),
    )
    return WorldMonitorImportSummary(
        import_run_id=import_run_id,
        source_path=str(resolved_source),
        source_file_count=len(source_rows),
        source_record_count=len(rows),
        imported_capture_count=imported_count,
        latest_source_timestamp=max((int(item["source_timestamp"]) for item in rows), default=None),
    )


def load_worldmonitor_units(
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
        ensure_worldmonitor_capture_schema(conn)
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
            FROM worldmonitor_capture_text_units u
            JOIN worldmonitor_capture_sources s ON s.capture_id = u.capture_id
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
                source_type="worldmonitor_capture",
                text=str(row["text"]),
            )
            for row in rows
            if str(row["text"]).strip()
        ]


def load_worldmonitor_activity_rows(
    conn: sqlite3.Connection,
    *,
    date: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    ensure_worldmonitor_capture_schema(conn)
    sql = """
        SELECT source_file, source_path, captured_at, source_row_id,
               source_kind, row_label, captured_date, content_sha1
        FROM worldmonitor_capture_sources
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
        out.append(
            {
                "ts": str(row["captured_at"] or ""),
                "kind": "worldmonitor_capture",
                "detail": str(row["row_label"] or row["source_row_id"] or ""),
                "source_path": str(row["source_path"] or row["source_file"] or ""),
                "meta": {
                    "captureSourceFile": str(row["source_file"] or ""),
                    "captureRowId": str(row["source_row_id"] or ""),
                    "sourceKind": "worldmonitor_capture",
                },
                "sourceKind": str(row["source_kind"] or ""),
                "rowLabel": str(row["row_label"] or ""),
            }
        )
    return out


def load_worldmonitor_import_runs(
    conn: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    ensure_worldmonitor_capture_schema(conn)
    rows = conn.execute(
        """
        SELECT
          r.import_run_id,
          r.source_path,
          r.imported_at,
          r.source_file_count,
          r.source_record_count,
          r.imported_capture_count,
          r.latest_source_timestamp,
          MIN(s.captured_at) AS first_captured_at,
          MAX(s.captured_at) AS last_captured_at,
          SUM(CASE WHEN TRIM(u.text) <> '' THEN 1 ELSE 0 END) AS text_unit_count
        FROM worldmonitor_import_runs r
        LEFT JOIN worldmonitor_capture_sources s ON s.import_run_id = r.import_run_id
        LEFT JOIN worldmonitor_capture_text_units u ON u.capture_id = s.capture_id
        GROUP BY r.import_run_id
        ORDER BY r.imported_at DESC, r.import_run_id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        imported = int(row["imported_capture_count"] or 0)
        text_units = int(row["text_unit_count"] or 0)
        out.append(
            {
                "importRunId": str(row["import_run_id"]),
                "sourcePath": str(row["source_path"] or ""),
                "importedAt": str(row["imported_at"] or ""),
                "sourceFileCount": int(row["source_file_count"] or 0),
                "sourceRecordCount": int(row["source_record_count"] or 0),
                "importedCaptureCount": imported,
                "latestSourceTimestamp": row["latest_source_timestamp"],
                "firstCapturedAt": row["first_captured_at"],
                "lastCapturedAt": row["last_captured_at"],
                "textCoverage": _coverage_payload(text_units, imported),
            }
        )
    return out


def build_worldmonitor_capture_summary(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    ensure_worldmonitor_capture_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    if import_run_id is not None:
        where.append("import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("captured_date = ?")
        params.append(date)
    if source_kind is not None:
        where.append("LOWER(source_kind) = LOWER(?)")
        params.append(source_kind)
    where_sql = f" WHERE {' AND '.join(where)}" if where else ""
    totals = conn.execute(
        f"""
        SELECT
          COUNT(*) AS capture_count,
          MIN(captured_at) AS first_captured_at,
          MAX(captured_at) AS last_captured_at,
          SUM(CASE WHEN TRIM(row_label) <> '' THEN 1 ELSE 0 END) AS label_count
        FROM worldmonitor_capture_sources
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int((totals["capture_count"] if totals is not None else 0) or 0)

    type_rows = conn.execute(
        f"""
        SELECT source_kind, COUNT(*) AS capture_count
        FROM worldmonitor_capture_sources
        {where_sql}
        GROUP BY source_kind
        ORDER BY capture_count DESC, source_kind ASC
        LIMIT 10
        """,
        tuple(params),
    ).fetchall()

    date_rows = conn.execute(
        f"""
        SELECT captured_date, COUNT(*) AS capture_count
        FROM worldmonitor_capture_sources
        {where_sql}
        GROUP BY captured_date
        ORDER BY captured_date DESC
        LIMIT 14
        """,
        tuple(params),
    ).fetchall()

    source_rows = conn.execute(
        f"""
        SELECT source_file, COUNT(*) AS capture_count
        FROM worldmonitor_capture_sources
        {where_sql}
        GROUP BY source_file
        ORDER BY capture_count DESC, source_file ASC
        LIMIT 10
        """,
        tuple(params),
    ).fetchall()

    label_count = int((totals["label_count"] if totals is not None else 0) or 0)

    return {
        "filters": {
            "importRunId": import_run_id,
            "date": date,
            "sourceKind": source_kind,
        },
        "captureCount": total,
        "firstCapturedAt": totals["first_captured_at"] if totals is not None else None,
        "lastCapturedAt": totals["last_captured_at"] if totals is not None else None,
        "labelCoverage": _coverage_payload(label_count, total) if total else _coverage_payload(0, 0),
        "countsBySourceKind": [
            {
                "sourceKind": str(row["source_kind"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in type_rows
        ],
        "countsByFile": [
            {
                "sourceFile": str(row["source_file"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in source_rows
        ],
        "countsByDate": [
            {
                "capturedDate": str(row["captured_date"] or ""),
                "captureCount": int(row["capture_count"] or 0),
            }
            for row in date_rows
        ],
    }


def query_worldmonitor_captures(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    ensure_worldmonitor_capture_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    if import_run_id is not None:
        where.append("s.import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("s.captured_date = ?")
        params.append(date)
    if source_kind is not None:
        where.append("LOWER(s.source_kind) = LOWER(?)")
        params.append(source_kind)
    if text_query is not None and text_query.strip():
        where.append("(LOWER(u.text) LIKE ? OR LOWER(s.row_label) LIKE ? OR LOWER(s.source_row_id) LIKE ?)")
        needle = f"%{text_query.strip().casefold()}%"
        params.extend([needle, needle, needle])
    sql = """
        SELECT s.capture_id, s.import_run_id, s.captured_at, s.captured_date,
               s.source_file, s.source_row_id, s.source_kind, s.row_label,
               u.text
        FROM worldmonitor_capture_sources s
        JOIN worldmonitor_capture_text_units u ON u.capture_id = s.capture_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.source_timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "captureId": str(row["capture_id"]),
                "importRunId": str(row["import_run_id"]),
                "capturedAt": str(row["captured_at"] or ""),
                "capturedDate": str(row["captured_date"] or ""),
                "sourceFile": str(row["source_file"] or ""),
                "sourceRowId": str(row["source_row_id"] or ""),
                "sourceKind": str(row["source_kind"] or ""),
                "rowLabel": str(row["row_label"] or ""),
                "textPreview": str(row["text"] or "")[:240],
            }
        )
    return out


def build_worldmonitor_chronology(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    ensure_worldmonitor_capture_schema(conn)
    where: list[str] = []
    params: list[Any] = []
    if import_run_id is not None:
        where.append("s.import_run_id = ?")
        params.append(import_run_id)
    if date is not None:
        where.append("s.captured_date = ?")
        params.append(date)
    if source_kind is not None:
        where.append("LOWER(s.source_kind) = LOWER(?)")
        params.append(source_kind)
    sql = """
        SELECT
          s.capture_id,
          s.import_run_id,
          s.captured_at,
          s.captured_date,
          s.source_file,
          s.source_row_id,
          s.source_kind,
          s.row_label,
          s.source_timestamp,
          s.content_sha1
        FROM worldmonitor_capture_sources s
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.source_timestamp ASC, s.capture_id ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, tuple(params)).fetchall()

    events: list[dict[str, Any]] = []
    semantic_order: dict[str, int] = {}
    for index, row in enumerate(rows, start=1):
        capture_id = str(row["capture_id"] or "").strip()
        if not capture_id:
            continue
        semantic_order[capture_id] = index
        events.append(
            {
                "event_id": capture_id,
                "source_event_ids": [capture_id],
                "event_type": "worldmonitor_capture",
                "primary_actor": str(row["source_kind"] or "worldmonitor_capture"),
                "object_text": str(row["row_label"] or row["source_row_id"] or ""),
                "time_start": str(row["captured_at"] or ""),
                "status": "captured",
            }
        )

    chronology = build_event_chronology(events, semantic_order=semantic_order)
    by_event_id = {str(row["event_id"]): row for row in chronology}

    enriched_chronology: list[dict[str, Any]] = []
    for row in rows:
        capture_id = str(row["capture_id"] or "").strip()
        chronology_row = dict(by_event_id.get(capture_id, {}))
        if not chronology_row:
            continue
        chronology_row.update(
            {
                "capture_id": capture_id,
                "captured_date": str(row["captured_date"] or ""),
                "source_kind": str(row["source_kind"] or ""),
                "row_label": str(row["row_label"] or ""),
                "source_row_id": str(row["source_row_id"] or ""),
                "source_timestamp": int(row["source_timestamp"] or 0),
            }
        )
        enriched_chronology.append(chronology_row)

    return {
        "filters": {
            "importRunId": import_run_id,
            "date": date,
            "sourceKind": source_kind,
        },
        "chronologyCount": len(enriched_chronology),
        "firstCapturedAt": enriched_chronology[0]["time_start"] if enriched_chronology else None,
        "lastCapturedAt": enriched_chronology[-1]["time_start"] if enriched_chronology else None,
        "chronology": enriched_chronology,
    }


def ensure_worldmonitor_observation_schema(conn: sqlite3.Connection) -> None:
    ensure_worldmonitor_capture_schema(conn)


def import_worldmonitor_source(
    conn: sqlite3.Connection,
    source_path: str | Path,
    import_run_id: str,
    *,
    limit: int | None = None,
) -> WorldMonitorImportSummary:
    return import_worldmonitor_data(
        conn,
        source_path=source_path,
        import_run_id=import_run_id,
        limit=limit,
    )


def build_worldmonitor_observation_summary(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    return build_worldmonitor_capture_summary(
        conn,
        import_run_id=import_run_id,
        date=date,
        source_kind=source_kind,
    )


def query_worldmonitor_observation_captures(
    conn: sqlite3.Connection,
    *,
    import_run_id: str | None = None,
    date: str | None = None,
    source_kind: str | None = None,
    text_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    return query_worldmonitor_captures(
        conn,
        import_run_id=import_run_id,
        date=date,
        source_kind=source_kind,
        text_query=text_query,
        limit=limit,
    )


WORLDMONITOR_OBSERVATION_LANE = ObservationLaneAdapter(
    lane_key="worldmonitor",
    source_unit_type="worldmonitor_capture",
    source_label="WorldMonitor",
    ensure_schema=ensure_worldmonitor_observation_schema,
    import_data=import_worldmonitor_source,
    load_units=load_worldmonitor_units,
    load_activity_rows=load_worldmonitor_activity_rows,
    load_import_runs=load_worldmonitor_import_runs,
    build_summary=build_worldmonitor_observation_summary,
    query_captures=query_worldmonitor_observation_captures,
)


__all__ = [
    "WORLDMONITOR_OBSERVATION_LANE",
    "WorldMonitorImportSummary",
    "ensure_worldmonitor_capture_schema",
    "ensure_worldmonitor_observation_schema",
    "import_worldmonitor_data",
    "import_worldmonitor_source",
    "load_worldmonitor_activity_rows",
    "load_worldmonitor_import_runs",
    "load_worldmonitor_units",
    "build_worldmonitor_chronology",
    "build_worldmonitor_capture_summary",
    "build_worldmonitor_observation_summary",
    "query_worldmonitor_captures",
    "query_worldmonitor_observation_captures",
]
