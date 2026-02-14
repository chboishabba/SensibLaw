from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_stable_json(obj: Any) -> str:
    return _sha256_bytes(_stable_json(obj).encode("utf-8"))


def _compute_run_id(
    *,
    timeline_sha256: str,
    profile_sha256: str,
    parser_signature_sha256: str,
    extractor_sha256: str,
) -> str:
    payload = {
        "kind": "wiki_timeline_aoo_run",
        "timeline_sha256": timeline_sha256,
        "profile_sha256": profile_sha256,
        "parser_signature_sha256": parser_signature_sha256,
        "extractor_sha256": extractor_sha256,
    }
    return "run:" + _sha256_stable_json(payload)


def _anchor_fields(anchor: Any) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str], Optional[str]]:
    if not isinstance(anchor, dict):
        return None, None, None, None, None
    year = anchor.get("year")
    month = anchor.get("month")
    day = anchor.get("day")
    precision = anchor.get("precision")
    kind = anchor.get("kind")
    try:
        year_i = int(year) if year is not None else None
    except Exception:
        year_i = None
    try:
        month_i = int(month) if month is not None else None
    except Exception:
        month_i = None
    try:
        day_i = int(day) if day is not None else None
    except Exception:
        day_i = None
    precision_s = str(precision) if precision is not None else None
    kind_s = str(kind) if kind is not None else None
    return year_i, month_i, day_i, precision_s, kind_s


@dataclass(frozen=True)
class WikiTimelineAooPersistResult:
    run_id: str
    timeline_sha256: str
    profile_sha256: str
    parser_signature_sha256: str
    extractor_sha256: str
    n_events: int


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    # Keep persistence maximally portable (WAL can fail on some filesystems/containers).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_aoo_runs (
          run_id TEXT PRIMARY KEY,
          generated_at TEXT NOT NULL,
          timeline_path TEXT,
          timeline_sha256 TEXT NOT NULL,
          candidates_path TEXT,
          candidates_sha256 TEXT,
          profile_path TEXT,
          profile_sha256 TEXT NOT NULL,
          parser_json TEXT NOT NULL,
          parser_signature_sha256 TEXT NOT NULL,
          extractor_sha256 TEXT NOT NULL,
          out_meta_json TEXT NOT NULL,
          n_events INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_aoo_events (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          anchor_year INTEGER,
          anchor_month INTEGER,
          anchor_day INTEGER,
          anchor_precision TEXT,
          anchor_kind TEXT,
          section TEXT,
          text TEXT,
          event_json TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id),
          FOREIGN KEY (run_id) REFERENCES wiki_timeline_aoo_runs(run_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_aoo_events_anchor_year ON wiki_timeline_aoo_events(anchor_year)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_aoo_events_anchor_ymd ON wiki_timeline_aoo_events(anchor_year, anchor_month, anchor_day)"
    )


def persist_wiki_timeline_aoo_run(
    *,
    db_path: Path,
    out_payload: Dict[str, Any],
    timeline_path: Optional[Path] = None,
    candidates_path: Optional[Path] = None,
    profile_path: Optional[Path] = None,
    extractor_path: Optional[Path] = None,
) -> WikiTimelineAooPersistResult:
    """Persist a wiki timeline AAO export into SQLite (canonical store).

    Contract: JSON is an export; DB is canonical persistence.
    Writes are idempotent keyed by (run_id, event_id).
    """

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    events = out_payload.get("events") or []
    if not isinstance(events, list):
        raise ValueError("out_payload.events must be a list")

    # Legacy/backfill tolerance: older JSON artifacts may omit generated_at.
    # This field is not part of run_id and is stored only for audit display.
    generated_at = str(out_payload.get("generated_at") or "").strip()
    if not generated_at:
        generated_at = "unknown"

    tl_sha = _sha256_file(Path(timeline_path)) if timeline_path else None
    if not tl_sha:
        # Fall back to hashing declared path if the file is unavailable (still deterministic,
        # but loses the strong content-addressing property).
        tl_sha = _sha256_bytes(str(timeline_path or "").encode("utf-8"))

    prof_sha = _sha256_file(Path(profile_path)) if profile_path else None
    if not prof_sha:
        # Use extraction_profile payload if present; else stable empty dict.
        prof_sha = _sha256_stable_json(out_payload.get("extraction_profile") or {})

    parser_json_obj = out_payload.get("parser") or {}
    parser_json = _stable_json(parser_json_obj)
    parser_sig_sha = _sha256_bytes(parser_json.encode("utf-8"))

    extractor_sha = _sha256_file(Path(extractor_path)) if extractor_path else None
    if not extractor_sha:
        extractor_sha = _sha256_bytes(b"wiki_timeline_aoo_extract@unknown")

    run_id = _compute_run_id(
        timeline_sha256=tl_sha,
        profile_sha256=prof_sha,
        parser_signature_sha256=parser_sig_sha,
        extractor_sha256=extractor_sha,
    )

    out_meta = dict(out_payload)
    out_meta.pop("events", None)
    out_meta_json = _stable_json(out_meta)

    cand_sha = _sha256_file(Path(candidates_path)) if candidates_path else None

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)

        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_timeline_aoo_runs(
              run_id, generated_at,
              timeline_path, timeline_sha256,
              candidates_path, candidates_sha256,
              profile_path, profile_sha256,
              parser_json, parser_signature_sha256,
              extractor_sha256,
              out_meta_json, n_events
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                generated_at,
                str(timeline_path) if timeline_path else None,
                tl_sha,
                str(candidates_path) if candidates_path else None,
                cand_sha,
                str(profile_path) if profile_path else None,
                prof_sha,
                parser_json,
                parser_sig_sha,
                extractor_sha,
                out_meta_json,
                int(len(events)),
            ),
        )

        rows: Iterable[Dict[str, Any]] = (e for e in events if isinstance(e, dict))
        for ev in rows:
            event_id = str(ev.get("event_id") or "").strip()
            if not event_id:
                continue
            year, month, day, precision, kind = _anchor_fields(ev.get("anchor"))
            conn.execute(
                """
                INSERT OR REPLACE INTO wiki_timeline_aoo_events(
                  run_id, event_id,
                  anchor_year, anchor_month, anchor_day,
                  anchor_precision, anchor_kind,
                  section, text,
                  event_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    event_id,
                    year,
                    month,
                    day,
                    precision,
                    kind,
                    str(ev.get("section") or "") if ev.get("section") is not None else None,
                    str(ev.get("text") or "") if ev.get("text") is not None else None,
                    _stable_json(ev),
                ),
            )

        conn.commit()

    return WikiTimelineAooPersistResult(
        run_id=run_id,
        timeline_sha256=tl_sha,
        profile_sha256=prof_sha,
        parser_signature_sha256=parser_sig_sha,
        extractor_sha256=extractor_sha,
        n_events=int(len([e for e in events if isinstance(e, dict) and str(e.get("event_id") or "").strip()])),
    )
