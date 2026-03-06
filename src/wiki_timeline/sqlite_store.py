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


def _anchor_fields(anchor: Any) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str], Optional[str], Optional[str]]:
    if not isinstance(anchor, dict):
        return None, None, None, None, None, None
    year = anchor.get("year")
    month = anchor.get("month")
    day = anchor.get("day")
    precision = anchor.get("precision")
    kind = anchor.get("kind")
    text = anchor.get("text")
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
    text_s = str(text) if text is not None else None
    return year_i, month_i, day_i, precision_s, kind_s, text_s


def _normalize_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def _pop_json(obj: dict[str, Any], key: str, fallback: Any) -> Any:
    value = obj.pop(key, fallback)
    return value


def _split_event_payload(ev: dict[str, Any]) -> dict[str, Any]:
    event = dict(ev)
    return {
        "event_id": _normalize_str(event.pop("event_id", None)) or "",
        "anchor": event.pop("anchor", None),
        "section": _normalize_str(event.pop("section", None)),
        "text": _normalize_str(event.pop("text", None)),
        "action": _normalize_str(event.pop("action", None)),
        "action_meta": _pop_json(event, "action_meta", None),
        "action_surface": _normalize_str(event.pop("action_surface", None)),
        "negation": _pop_json(event, "negation", None),
        "purpose": _normalize_str(event.pop("purpose", None)),
        "claim_bearing": bool(event.pop("claim_bearing", False)),
        "actors": _pop_json(event, "actors", []),
        "links": _pop_json(event, "links", []),
        "links_para": _pop_json(event, "links_para", []),
        "objects": _pop_json(event, "objects", []),
        "entity_objects": _pop_json(event, "entity_objects", []),
        "modifier_objects": _pop_json(event, "modifier_objects", []),
        "numeric_objects": _pop_json(event, "numeric_objects", []),
        "steps": _pop_json(event, "steps", []),
        "citations": _pop_json(event, "citations", []),
        "attributions": _pop_json(event, "attributions", []),
        "chains": _pop_json(event, "chains", []),
        "span_candidates": _pop_json(event, "span_candidates", []),
        "numeric_claims": _pop_json(event, "numeric_claims", []),
        "claim_step_indices": _pop_json(event, "claim_step_indices", []),
        "residual": event,
    }


def _load_json(text: Any) -> Any:
    if text is None:
        return None
    try:
        return json.loads(str(text))
    except Exception:
        return None


@dataclass(frozen=True)
class WikiTimelineAooPersistResult:
    run_id: str
    timeline_sha256: str
    profile_sha256: str
    parser_signature_sha256: str
    extractor_sha256: str
    n_events: int


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
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
    _ensure_column(conn, "wiki_timeline_aoo_events", "anchor_text", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "section_id", "INTEGER")
    _ensure_column(conn, "wiki_timeline_aoo_events", "action_id", "INTEGER")
    _ensure_column(conn, "wiki_timeline_aoo_events", "action_surface", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "action_meta_json", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "negation_kind", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "negation_scope", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "negation_source", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "purpose", "TEXT")
    _ensure_column(conn, "wiki_timeline_aoo_events", "claim_bearing", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "wiki_timeline_aoo_events", "residual_json", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_sections (
          section_id INTEGER PRIMARY KEY,
          label TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_actions (
          action_id INTEGER PRIMARY KEY,
          lemma TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_actors (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          actor_order INTEGER NOT NULL,
          label TEXT,
          resolved TEXT,
          role TEXT,
          source TEXT,
          PRIMARY KEY (run_id, event_id, actor_order),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_links (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          link_order INTEGER NOT NULL,
          title TEXT NOT NULL,
          lane TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, lane, link_order),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_objects (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          object_order INTEGER NOT NULL,
          title TEXT,
          source TEXT,
          object_lane TEXT NOT NULL,
          resolver_hints_json TEXT,
          PRIMARY KEY (run_id, event_id, object_lane, object_order),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_steps (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          step_index INTEGER NOT NULL,
          action_id INTEGER,
          action_surface TEXT,
          action_meta_json TEXT,
          negation_kind TEXT,
          negation_scope TEXT,
          negation_source TEXT,
          purpose TEXT,
          claim_bearing INTEGER NOT NULL DEFAULT 0,
          residual_json TEXT,
          PRIMARY KEY (run_id, event_id, step_index),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id),
          FOREIGN KEY (action_id) REFERENCES wiki_timeline_actions(action_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_step_subjects (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          step_index INTEGER NOT NULL,
          subject_order INTEGER NOT NULL,
          label TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, step_index, subject_order),
          FOREIGN KEY (run_id, event_id, step_index) REFERENCES wiki_timeline_event_steps(run_id, event_id, step_index)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_step_objects (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          step_index INTEGER NOT NULL,
          object_order INTEGER NOT NULL,
          title TEXT NOT NULL,
          object_lane TEXT NOT NULL,
          source TEXT,
          PRIMARY KEY (run_id, event_id, step_index, object_lane, object_order),
          FOREIGN KEY (run_id, event_id, step_index) REFERENCES wiki_timeline_event_steps(run_id, event_id, step_index)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_lists (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          list_name TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          item_json TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, list_name, item_order),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_run_lists (
          run_id TEXT NOT NULL,
          list_name TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          item_json TEXT NOT NULL,
          PRIMARY KEY (run_id, list_name, item_order),
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_aoo_events_section_id ON wiki_timeline_aoo_events(section_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_aoo_events_action_id ON wiki_timeline_aoo_events(action_id)"
    )


def _get_or_create_id(conn: sqlite3.Connection, table: str, id_col: str, key_col: str, value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    row = conn.execute(f"SELECT {id_col} AS id FROM {table} WHERE {key_col} = ?", (value,)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(f"INSERT INTO {table}({key_col}) VALUES (?)", (value,))
    return int(cur.lastrowid)


def _clear_event_rows(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM wiki_timeline_step_subjects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_step_objects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_steps WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_actors WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_links WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_objects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_lists WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_run_lists WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_aoo_events WHERE run_id = ?", (run_id,))


def _insert_list_rows(conn: sqlite3.Connection, run_id: str, event_id: str, list_name: str, items: Any) -> None:
    if not isinstance(items, list):
        return
    for item_order, item in enumerate(items):
        conn.execute(
            """
            INSERT INTO wiki_timeline_event_lists(run_id, event_id, list_name, item_order, item_json)
            VALUES (?,?,?,?,?)
            """,
            (run_id, event_id, list_name, item_order, _stable_json(item)),
        )


def _insert_run_list_rows(conn: sqlite3.Connection, run_id: str, list_name: str, items: Any) -> None:
    if not isinstance(items, list):
        return
    for item_order, item in enumerate(items):
        conn.execute(
            """
            INSERT INTO wiki_timeline_run_lists(run_id, list_name, item_order, item_json)
            VALUES (?,?,?,?)
            """,
            (run_id, list_name, item_order, _stable_json(item)),
        )


def _persist_event(conn: sqlite3.Connection, run_id: str, ev: dict[str, Any]) -> None:
    split = _split_event_payload(ev)
    event_id = split["event_id"]
    if not event_id:
        return

    year, month, day, precision, kind, anchor_text = _anchor_fields(split["anchor"])
    section_id = _get_or_create_id(conn, "wiki_timeline_sections", "section_id", "label", split["section"])
    action_id = _get_or_create_id(conn, "wiki_timeline_actions", "action_id", "lemma", split["action"])
    neg = split["negation"] if isinstance(split["negation"], dict) else {}

    conn.execute(
        """
        INSERT OR REPLACE INTO wiki_timeline_aoo_events(
          run_id, event_id,
          anchor_year, anchor_month, anchor_day,
          anchor_precision, anchor_kind, section, text, event_json,
          anchor_text, section_id, action_id, action_surface, action_meta_json,
          negation_kind, negation_scope, negation_source, purpose, claim_bearing, residual_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            event_id,
            year,
            month,
            day,
            precision,
            kind,
            split["section"],
            split["text"],
            "{}",
            anchor_text,
            section_id,
            action_id,
            split["action_surface"],
            _stable_json(split["action_meta"]) if split["action_meta"] is not None else None,
            _normalize_str(neg.get("kind")),
            _normalize_str(neg.get("scope")),
            _normalize_str(neg.get("source")),
            split["purpose"],
            _normalize_bool(split["claim_bearing"]),
            _stable_json(split["residual"]) if split["residual"] else None,
        ),
    )

    for actor_order, actor in enumerate(split["actors"] if isinstance(split["actors"], list) else []):
        if not isinstance(actor, dict):
            continue
        conn.execute(
            """
            INSERT INTO wiki_timeline_event_actors(run_id, event_id, actor_order, label, resolved, role, source)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                run_id,
                event_id,
                actor_order,
                _normalize_str(actor.get("label")),
                _normalize_str(actor.get("resolved")),
                _normalize_str(actor.get("role")),
                _normalize_str(actor.get("source")),
            ),
        )

    for lane_name in ("links", "links_para"):
        links = split[lane_name]
        if not isinstance(links, list):
            continue
        for link_order, title in enumerate(links):
            title_text = _normalize_str(title)
            if not title_text:
                continue
            conn.execute(
                """
                INSERT INTO wiki_timeline_event_links(run_id, event_id, link_order, title, lane)
                VALUES (?,?,?,?,?)
                """,
                (run_id, event_id, link_order, title_text, lane_name),
            )

    for lane_name in ("entity_objects", "modifier_objects", "numeric_objects"):
        objs = split[lane_name]
        if not isinstance(objs, list):
            continue
        for object_order, title in enumerate(objs):
            title_text = _normalize_str(title)
            if not title_text:
                continue
            conn.execute(
                """
                INSERT INTO wiki_timeline_event_objects(run_id, event_id, object_order, title, source, object_lane, resolver_hints_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (run_id, event_id, object_order, title_text, None, lane_name, None),
            )

    raw_objects = split["objects"] if isinstance(split["objects"], list) else []
    for object_order, obj in enumerate(raw_objects):
        if isinstance(obj, dict):
            title = _normalize_str(obj.get("title"))
            if not title:
                continue
            conn.execute(
                """
                INSERT INTO wiki_timeline_event_objects(run_id, event_id, object_order, title, source, object_lane, resolver_hints_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    event_id,
                    object_order,
                    title,
                    _normalize_str(obj.get("source")),
                    "objects",
                    _stable_json(obj.get("resolver_hints")) if obj.get("resolver_hints") is not None else None,
                ),
            )
        else:
            title = _normalize_str(obj)
            if title:
                conn.execute(
                    """
                    INSERT INTO wiki_timeline_event_objects(run_id, event_id, object_order, title, source, object_lane, resolver_hints_json)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (run_id, event_id, object_order, title, None, "objects", None),
                )

    steps = split["steps"] if isinstance(split["steps"], list) else []
    for step_index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        step_action_id = _get_or_create_id(conn, "wiki_timeline_actions", "action_id", "lemma", _normalize_str(step.get("action")))
        step_neg = step.get("negation") if isinstance(step.get("negation"), dict) else {}
        step_copy = dict(step)
        step_copy.pop("action", None)
        step_copy.pop("action_meta", None)
        step_copy.pop("action_surface", None)
        step_copy.pop("negation", None)
        step_copy.pop("purpose", None)
        step_copy.pop("claim_bearing", None)
        step_copy.pop("subjects", None)
        step_copy.pop("objects", None)
        step_copy.pop("entity_objects", None)
        step_copy.pop("modifier_objects", None)
        step_copy.pop("numeric_objects", None)
        conn.execute(
            """
            INSERT INTO wiki_timeline_event_steps(
              run_id, event_id, step_index, action_id, action_surface, action_meta_json,
              negation_kind, negation_scope, negation_source, purpose, claim_bearing, residual_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                event_id,
                step_index,
                step_action_id,
                _normalize_str(step.get("action_surface")),
                _stable_json(step.get("action_meta")) if step.get("action_meta") is not None else None,
                _normalize_str(step_neg.get("kind")),
                _normalize_str(step_neg.get("scope")),
                _normalize_str(step_neg.get("source")),
                _normalize_str(step.get("purpose")),
                _normalize_bool(step.get("claim_bearing")),
                _stable_json(step_copy) if step_copy else None,
            ),
        )
        subjects = step.get("subjects") if isinstance(step.get("subjects"), list) else []
        for subject_order, label in enumerate(subjects):
            label_text = _normalize_str(label)
            if not label_text:
                continue
            conn.execute(
                """
                INSERT INTO wiki_timeline_step_subjects(run_id, event_id, step_index, subject_order, label)
                VALUES (?,?,?,?,?)
                """,
                (run_id, event_id, step_index, subject_order, label_text),
            )
        for lane_name in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            lane_items = step.get(lane_name) if isinstance(step.get(lane_name), list) else []
            for object_order, title in enumerate(lane_items):
                title_text = _normalize_str(title)
                if not title_text:
                    continue
                conn.execute(
                    """
                    INSERT INTO wiki_timeline_step_objects(run_id, event_id, step_index, object_order, title, object_lane, source)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (run_id, event_id, step_index, object_order, title_text, lane_name, None),
                )

    for list_name in ("citations", "attributions", "chains", "span_candidates", "numeric_claims", "claim_step_indices"):
        _insert_list_rows(conn, run_id, event_id, list_name, split[list_name])


def persist_normalized_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    out_payload: Dict[str, Any],
) -> None:
    _clear_event_rows(conn, run_id)
    rows: Iterable[Dict[str, Any]] = (e for e in (out_payload.get("events") or []) if isinstance(e, dict))
    for ev in rows:
        _persist_event(conn, run_id, ev)
    _insert_run_list_rows(conn, run_id, "fact_timeline", out_payload.get("fact_timeline"))


def _load_event_from_normalized(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    event: dict[str, Any] = {}
    residual = _load_json(row["residual_json"])
    if isinstance(residual, dict):
        event.update(residual)
    event["event_id"] = str(row["event_id"])
    event["anchor"] = {
        "year": int(row["anchor_year"]) if row["anchor_year"] is not None else None,
        "month": int(row["anchor_month"]) if row["anchor_month"] is not None else None,
        "day": int(row["anchor_day"]) if row["anchor_day"] is not None else None,
        "precision": row["anchor_precision"],
        "kind": row["anchor_kind"],
        "text": row["anchor_text"],
    }
    event["section"] = row["section"]
    event["text"] = row["text"]
    if row["action_id"] is not None:
        action_row = conn.execute("SELECT lemma FROM wiki_timeline_actions WHERE action_id = ?", (row["action_id"],)).fetchone()
        event["action"] = action_row["lemma"] if action_row else None
    if row["action_meta_json"] is not None:
        event["action_meta"] = _load_json(row["action_meta_json"])
    if row["action_surface"] is not None:
        event["action_surface"] = row["action_surface"]
    if row["purpose"] is not None:
        event["purpose"] = row["purpose"]
    event["claim_bearing"] = bool(row["claim_bearing"])
    negation = {}
    if row["negation_kind"] is not None:
        negation["kind"] = row["negation_kind"]
    if row["negation_scope"] is not None:
        negation["scope"] = row["negation_scope"]
    if row["negation_source"] is not None:
        negation["source"] = row["negation_source"]
    if negation:
        event["negation"] = negation

    actors = conn.execute(
        """
        SELECT label, resolved, role, source
        FROM wiki_timeline_event_actors
        WHERE run_id = ? AND event_id = ?
        ORDER BY actor_order
        """,
        (row["run_id"], row["event_id"]),
    ).fetchall()
    if actors:
        event["actors"] = [
            {
                "label": a["label"],
                "resolved": a["resolved"],
                "role": a["role"],
                "source": a["source"],
            }
            for a in actors
        ]

    for lane_name in ("links", "links_para"):
        link_rows = conn.execute(
            """
            SELECT title
            FROM wiki_timeline_event_links
            WHERE run_id = ? AND event_id = ? AND lane = ?
            ORDER BY link_order
            """,
            (row["run_id"], row["event_id"], lane_name),
        ).fetchall()
        if link_rows:
            event[lane_name] = [str(link["title"]) for link in link_rows]

    object_rows = conn.execute(
        """
        SELECT object_lane, title, source, resolver_hints_json
        FROM wiki_timeline_event_objects
        WHERE run_id = ? AND event_id = ?
        ORDER BY object_lane, object_order
        """,
        (row["run_id"], row["event_id"]),
    ).fetchall()
    lane_map: dict[str, list[Any]] = {}
    for obj in object_rows:
        lane = str(obj["object_lane"])
        lane_map.setdefault(lane, [])
        if lane == "objects":
            entry: dict[str, Any] = {"title": obj["title"], "source": obj["source"]}
            hints = _load_json(obj["resolver_hints_json"])
            if hints is not None:
                entry["resolver_hints"] = hints
            lane_map[lane].append(entry)
        else:
            lane_map[lane].append(obj["title"])
    event.update(lane_map)

    step_rows = conn.execute(
        """
        SELECT step_index, action_id, action_surface, action_meta_json,
               negation_kind, negation_scope, negation_source, purpose, claim_bearing, residual_json
        FROM wiki_timeline_event_steps
        WHERE run_id = ? AND event_id = ?
        ORDER BY step_index
        """,
        (row["run_id"], row["event_id"]),
    ).fetchall()
    if step_rows:
        steps: list[dict[str, Any]] = []
        for step in step_rows:
            step_payload: dict[str, Any] = {}
            residual_step = _load_json(step["residual_json"])
            if isinstance(residual_step, dict):
                step_payload.update(residual_step)
            if step["action_id"] is not None:
                action_row = conn.execute("SELECT lemma FROM wiki_timeline_actions WHERE action_id = ?", (step["action_id"],)).fetchone()
                step_payload["action"] = action_row["lemma"] if action_row else None
            if step["action_meta_json"] is not None:
                step_payload["action_meta"] = _load_json(step["action_meta_json"])
            if step["action_surface"] is not None:
                step_payload["action_surface"] = step["action_surface"]
            if step["purpose"] is not None:
                step_payload["purpose"] = step["purpose"]
            step_payload["claim_bearing"] = bool(step["claim_bearing"])
            step_neg = {}
            if step["negation_kind"] is not None:
                step_neg["kind"] = step["negation_kind"]
            if step["negation_scope"] is not None:
                step_neg["scope"] = step["negation_scope"]
            if step["negation_source"] is not None:
                step_neg["source"] = step["negation_source"]
            if step_neg:
                step_payload["negation"] = step_neg
            subjects = conn.execute(
                """
                SELECT label FROM wiki_timeline_step_subjects
                WHERE run_id = ? AND event_id = ? AND step_index = ?
                ORDER BY subject_order
                """,
                (row["run_id"], row["event_id"], step["step_index"]),
            ).fetchall()
            if subjects:
                step_payload["subjects"] = [s["label"] for s in subjects]
            step_objs = conn.execute(
                """
                SELECT object_lane, title
                FROM wiki_timeline_step_objects
                WHERE run_id = ? AND event_id = ? AND step_index = ?
                ORDER BY object_lane, object_order
                """,
                (row["run_id"], row["event_id"], step["step_index"]),
            ).fetchall()
            if step_objs:
                lane_to_objs: dict[str, list[str]] = {}
                for obj in step_objs:
                    lane_to_objs.setdefault(str(obj["object_lane"]), []).append(str(obj["title"]))
                step_payload.update(lane_to_objs)
            steps.append(step_payload)
        event["steps"] = steps

    list_rows = conn.execute(
        """
        SELECT list_name, item_json
        FROM wiki_timeline_event_lists
        WHERE run_id = ? AND event_id = ?
        ORDER BY list_name, item_order
        """,
        (row["run_id"], row["event_id"]),
    ).fetchall()
    if list_rows:
        grouped: dict[str, list[Any]] = {}
        for item in list_rows:
            grouped.setdefault(str(item["list_name"]), []).append(_load_json(item["item_json"]))
        event.update(grouped)

    return event


def backfill_normalized_run(conn: sqlite3.Connection, run_id: str) -> None:
    rows = conn.execute(
        """
        SELECT event_id, event_json
        FROM wiki_timeline_aoo_events
        WHERE run_id = ?
        ORDER BY anchor_year, anchor_month, anchor_day, event_id
        """,
        (run_id,),
    ).fetchall()
    if not rows:
        return
    normalized_exists = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM wiki_timeline_aoo_events
        WHERE run_id = ?
          AND (
            event_json = '{}'
            OR residual_json IS NOT NULL
            OR action_id IS NOT NULL
            OR section_id IS NOT NULL
            OR anchor_text IS NOT NULL
          )
        """,
        (run_id,),
    ).fetchone()["c"]
    if normalized_exists:
        return
    run_row = conn.execute("SELECT out_meta_json FROM wiki_timeline_aoo_runs WHERE run_id = ?", (run_id,)).fetchone()
    out_meta = _load_json(run_row["out_meta_json"]) if run_row else {}
    out_payload = dict(out_meta) if isinstance(out_meta, dict) else {}
    events: list[dict[str, Any]] = []
    for row in rows:
        event_payload = _load_json(row["event_json"])
        if isinstance(event_payload, dict):
            events.append(event_payload)
    out_payload["events"] = events
    db_file = None
    try:
        db_row = conn.execute("PRAGMA database_list").fetchone()
        if db_row is not None and len(db_row) >= 3:
            db_file = db_row[2]
    except Exception:
        db_file = None
    if db_file:
        with sqlite3.connect(str(db_file)) as write_conn:
            write_conn.row_factory = sqlite3.Row
            _ensure_schema(write_conn)
            persist_normalized_run(write_conn, run_id=run_id, out_payload=out_payload)
            write_conn.commit()
    else:
        persist_normalized_run(conn, run_id=run_id, out_payload=out_payload)


def load_run_payload_from_normalized(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    _ensure_schema(conn)
    row = conn.execute(
        """
        SELECT run_id, generated_at, out_meta_json, parser_json, timeline_path
        FROM wiki_timeline_aoo_runs
        WHERE run_id=?
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return None
    out_meta = _load_json(row["out_meta_json"]) if row["out_meta_json"] else {}
    parser = _load_json(row["parser_json"]) if row["parser_json"] else {}

    def _load_legacy_payload() -> dict[str, Any]:
        legacy_payload = dict(out_meta) if isinstance(out_meta, dict) else {}
        legacy_payload["parser"] = parser
        legacy_payload["generated_at"] = str(legacy_payload.get("generated_at") or row["generated_at"] or "unknown")
        legacy_payload["run_id"] = str(row["run_id"])
        legacy_payload["source_timeline"] = legacy_payload.get("source_timeline") or {"path": row["timeline_path"], "snapshot": None}
        ev_rows = conn.execute(
            """
            SELECT event_json
            FROM wiki_timeline_aoo_events
            WHERE run_id = ?
            ORDER BY CASE WHEN anchor_year IS NULL OR anchor_year = 0 THEN 9999 ELSE anchor_year END,
                     COALESCE(anchor_month, 99),
                     COALESCE(anchor_day, 99),
                     event_id
            """,
            (run_id,),
        ).fetchall()
        legacy_payload["events"] = [ev for ev in (_load_json(ev_row["event_json"]) for ev_row in ev_rows) if isinstance(ev, dict)]
        return legacy_payload

    try:
        backfill_normalized_run(conn, run_id)
    except Exception:
        return _load_legacy_payload()

    payload = dict(out_meta) if isinstance(out_meta, dict) else {}
    payload["parser"] = parser
    payload["generated_at"] = str(payload.get("generated_at") or row["generated_at"] or "unknown")
    payload["run_id"] = str(row["run_id"])
    payload["source_timeline"] = payload.get("source_timeline") or {"path": row["timeline_path"], "snapshot": None}

    event_rows = conn.execute(
        """
        SELECT run_id, event_id, anchor_year, anchor_month, anchor_day, anchor_precision,
               anchor_kind, anchor_text, section, text, action_id, action_surface,
               action_meta_json, negation_kind, negation_scope, negation_source, purpose,
               claim_bearing, residual_json
        FROM wiki_timeline_aoo_events
        WHERE run_id = ?
        ORDER BY CASE WHEN anchor_year IS NULL OR anchor_year = 0 THEN 9999 ELSE anchor_year END,
                 COALESCE(anchor_month, 99),
                 COALESCE(anchor_day, 99),
                 event_id
        """,
        (run_id,),
    ).fetchall()
    if not event_rows:
        return _load_legacy_payload()
    payload["events"] = [_load_event_from_normalized(conn, event_row) for event_row in event_rows]

    run_list_rows = conn.execute(
        """
        SELECT list_name, item_json
        FROM wiki_timeline_run_lists
        WHERE run_id = ?
        ORDER BY list_name, item_order
        """,
        (run_id,),
    ).fetchall()
    if run_list_rows:
        grouped: dict[str, list[Any]] = {}
        for item in run_list_rows:
            grouped.setdefault(str(item["list_name"]), []).append(_load_json(item["item_json"]))
        payload.update(grouped)

    return payload


def persist_wiki_timeline_aoo_run(
    *,
    db_path: Path,
    out_payload: Dict[str, Any],
    timeline_path: Optional[Path] = None,
    candidates_path: Optional[Path] = None,
    profile_path: Optional[Path] = None,
    extractor_path: Optional[Path] = None,
    run_id_override: Optional[str] = None,
) -> WikiTimelineAooPersistResult:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    events = out_payload.get("events") or []
    if not isinstance(events, list):
        raise ValueError("out_payload.events must be a list")

    generated_at = str(out_payload.get("generated_at") or "").strip() or "unknown"

    tl_sha = _sha256_file(Path(timeline_path)) if timeline_path else None
    if not tl_sha:
        tl_sha = _sha256_bytes(str(timeline_path or "").encode("utf-8"))

    prof_sha = _sha256_file(Path(profile_path)) if profile_path else None
    if not prof_sha:
        prof_sha = _sha256_stable_json(out_payload.get("extraction_profile") or {})

    parser_json_obj = out_payload.get("parser") or {}
    parser_json = _stable_json(parser_json_obj)
    parser_sig_sha = _sha256_bytes(parser_json.encode("utf-8"))

    extractor_sha = _sha256_file(Path(extractor_path)) if extractor_path else None
    if not extractor_sha:
        extractor_sha = _sha256_bytes(b"wiki_timeline_aoo_extract@unknown")

    run_id = run_id_override or _compute_run_id(
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
        persist_normalized_run(conn, run_id=run_id, out_payload=out_payload)
        conn.commit()

    return WikiTimelineAooPersistResult(
        run_id=run_id,
        timeline_sha256=tl_sha,
        profile_sha256=prof_sha,
        parser_signature_sha256=parser_sig_sha,
        extractor_sha256=extractor_sha,
        n_events=int(len([e for e in events if isinstance(e, dict) and str(e.get("event_id") or "").strip()])),
    )
