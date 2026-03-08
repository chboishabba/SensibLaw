from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from src.text.lexeme_index import collect_lexeme_occurrences


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


def _encode_value_type(value: Any) -> tuple[str, str]:
    if value is None:
        return "null", ""
    if isinstance(value, bool):
        return "bool", "1" if value else "0"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int", str(value)
    if isinstance(value, float):
        return "float", repr(value)
    return "text", str(value)


def _decode_value_type(value_type: str, value_text: str) -> Any:
    if value_type == "null":
        return None
    if value_type == "bool":
        return value_text == "1"
    if value_type == "int":
        return int(value_text)
    if value_type == "float":
        return float(value_text)
    return value_text


def _flatten_value_paths(value: Any, prefix: str = "$") -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            rows.extend(_flatten_value_paths(value[key], f"{prefix}/{key}"))
        return rows
    if isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_flatten_value_paths(item, f"{prefix}/{index}"))
        return rows
    value_type, value_text = _encode_value_type(value)
    rows.append((prefix, value_type, value_text))
    return rows


def _path_segment_key(segment: str) -> int | str:
    return int(segment) if segment.isdigit() else segment


def _materialize_path_rows(rows: list[tuple[str, str, str]]) -> Any:
    if not rows:
        return None
    root_value: Any = None
    for path, value_type, value_text in rows:
        if path == "$":
            root_value = _decode_value_type(value_type, value_text)
            continue
        segments = [segment for segment in path.split("/") if segment and segment != "$"]
        if root_value is None:
            root_value = [] if segments and segments[0].isdigit() else {}
        cursor = root_value
        for depth, segment in enumerate(segments):
            key = _path_segment_key(segment)
            last = depth == len(segments) - 1
            next_is_index = depth + 1 < len(segments) and segments[depth + 1].isdigit()
            if isinstance(key, int):
                assert isinstance(cursor, list)
                while len(cursor) <= key:
                    cursor.append(None)
                if last:
                    cursor[key] = _decode_value_type(value_type, value_text)
                else:
                    if cursor[key] is None:
                        cursor[key] = [] if next_is_index else {}
                    cursor = cursor[key]
            else:
                assert isinstance(cursor, dict)
                if last:
                    cursor[key] = _decode_value_type(value_type, value_text)
                else:
                    if key not in cursor or cursor[key] is None:
                        cursor[key] = [] if next_is_index else {}
                    cursor = cursor[key]
    return root_value


def _insert_path_rows(
    conn: sqlite3.Connection,
    table: str,
    base_columns: dict[str, Any],
    value: Any,
) -> None:
    rows = _flatten_value_paths(value)
    if not rows:
        return
    columns = list(base_columns.keys()) + ["path", "value_type", "value_text"]
    placeholders = ",".join("?" for _ in columns)
    sql = f"INSERT INTO {table}({', '.join(columns)}) VALUES ({placeholders})"
    conn.executemany(
        sql,
        [tuple(base_columns.values()) + (path, value_type, value_text) for path, value_type, value_text in rows],
    )


def _field_rows_to_value(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...],
) -> Any:
    rows = conn.execute(query, params).fetchall()
    return _materialize_path_rows([(str(row["path"]), str(row["value_type"]), str(row["value_text"])) for row in rows])


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


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


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
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_object_field_values (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          object_lane TEXT NOT NULL,
          object_order INTEGER NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_text TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, object_lane, object_order, path),
          FOREIGN KEY (run_id, event_id, object_lane, object_order)
            REFERENCES wiki_timeline_event_objects(run_id, event_id, object_lane, object_order)
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
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_field_values (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_text TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, path),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_step_field_values (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          step_index INTEGER NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_text TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, step_index, path),
          FOREIGN KEY (run_id, event_id, step_index)
            REFERENCES wiki_timeline_event_steps(run_id, event_id, step_index)
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
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_list_field_values (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          list_name TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_text TEXT NOT NULL,
          PRIMARY KEY (run_id, event_id, list_name, item_order, path),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_run_list_field_values (
          run_id TEXT NOT NULL,
          list_name TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          path TEXT NOT NULL,
          value_type TEXT NOT NULL,
          value_text TEXT NOT NULL,
          PRIMARY KEY (run_id, list_name, item_order, path),
          FOREIGN KEY (run_id) REFERENCES wiki_timeline_aoo_runs(run_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_structural_atoms (
          atom_id INTEGER PRIMARY KEY,
          norm_text TEXT NOT NULL,
          norm_kind TEXT NOT NULL,
          UNIQUE (norm_text, norm_kind)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_timeline_event_structural_atoms (
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          occ_id INTEGER NOT NULL,
          atom_id INTEGER NOT NULL,
          start_char INTEGER NOT NULL,
          end_char INTEGER NOT NULL,
          token_index INTEGER,
          PRIMARY KEY (run_id, event_id, occ_id),
          FOREIGN KEY (run_id, event_id) REFERENCES wiki_timeline_aoo_events(run_id, event_id),
          FOREIGN KEY (atom_id) REFERENCES wiki_timeline_structural_atoms(atom_id)
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_structural_atoms_kind ON wiki_timeline_structural_atoms(norm_kind)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_event_structural_atoms_atom ON wiki_timeline_event_structural_atoms(atom_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wiki_timeline_event_structural_atoms_span ON wiki_timeline_event_structural_atoms(run_id, event_id, start_char, end_char)"
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
    conn.execute("DELETE FROM wiki_timeline_event_structural_atoms WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_field_values WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_step_field_values WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_object_field_values WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_step_subjects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_step_objects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_steps WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_actors WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_links WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_objects WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_event_list_field_values WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_run_list_field_values WHERE run_id = ?", (run_id,))
    if _table_exists(conn, "wiki_timeline_event_lists"):
        conn.execute("DELETE FROM wiki_timeline_event_lists WHERE run_id = ?", (run_id,))
    if _table_exists(conn, "wiki_timeline_run_lists"):
        conn.execute("DELETE FROM wiki_timeline_run_lists WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM wiki_timeline_aoo_events WHERE run_id = ?", (run_id,))


def _persist_structural_atoms(conn: sqlite3.Connection, run_id: str, event_id: str, text: Optional[str]) -> None:
    if not text:
        return
    structural_kinds = {
        "case_ref",
        "section_ref",
        "subsection_ref",
        "act_ref",
        "paragraph_ref",
        "article_ref",
        "instrument_ref",
        "institution_ref",
        "court_ref",
    }
    occurrences = [
        occ
        for occ in collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
        if occ.kind in structural_kinds
    ]
    if not occurrences:
        return
    atom_keys = sorted({(occ.norm_text, occ.kind) for occ in occurrences})
    conn.executemany(
        "INSERT OR IGNORE INTO wiki_timeline_structural_atoms(norm_text, norm_kind) VALUES (?, ?)",
        atom_keys,
    )
    placeholders = ",".join("(?, ?)" for _ in atom_keys)
    flat: list[str] = []
    for norm_text, norm_kind in atom_keys:
        flat.extend([norm_text, norm_kind])
    rows = conn.execute(
        f"SELECT atom_id, norm_text, norm_kind FROM wiki_timeline_structural_atoms WHERE (norm_text, norm_kind) IN ({placeholders})",
        flat,
    ).fetchall()
    atom_ids = {(row["norm_text"], row["norm_kind"]): int(row["atom_id"]) for row in rows}
    conn.executemany(
        """
        INSERT INTO wiki_timeline_event_structural_atoms(
          run_id, event_id, occ_id, atom_id, start_char, end_char, token_index
        ) VALUES (?,?,?,?,?,?,?)
        """,
        [
            (
                run_id,
                event_id,
                index,
                atom_ids[(occ.norm_text, occ.kind)],
                occ.start_char,
                occ.end_char,
                index - 1,
            )
            for index, occ in enumerate(occurrences, start=1)
        ],
    )


def _insert_list_rows(conn: sqlite3.Connection, run_id: str, event_id: str, list_name: str, items: Any) -> None:
    if not isinstance(items, list):
        return
    for item_order, item in enumerate(items):
        _insert_path_rows(
            conn,
            "wiki_timeline_event_list_field_values",
            {
                "run_id": run_id,
                "event_id": event_id,
                "list_name": list_name,
                "item_order": item_order,
            },
            item,
        )

def _insert_run_list_rows(conn: sqlite3.Connection, run_id: str, list_name: str, items: Any) -> None:
    if not isinstance(items, list):
        return
    for item_order, item in enumerate(items):
        _insert_path_rows(
            conn,
            "wiki_timeline_run_list_field_values",
            {
                "run_id": run_id,
                "list_name": list_name,
                "item_order": item_order,
            },
            item,
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
            None,
            _normalize_str(neg.get("kind")),
            _normalize_str(neg.get("scope")),
            _normalize_str(neg.get("source")),
            split["purpose"],
            _normalize_bool(split["claim_bearing"]),
            None,
        ),
    )
    _persist_structural_atoms(conn, run_id, event_id, split["text"])
    if split["action_meta"] is not None:
        _insert_path_rows(
            conn,
            "wiki_timeline_event_field_values",
            {"run_id": run_id, "event_id": event_id},
            {"action_meta": split["action_meta"]},
        )
    if split["residual"]:
        _insert_path_rows(
            conn,
            "wiki_timeline_event_field_values",
            {"run_id": run_id, "event_id": event_id},
            split["residual"],
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
                    None,
                ),
            )
            if obj.get("resolver_hints") is not None:
                _insert_path_rows(
                    conn,
                    "wiki_timeline_event_object_field_values",
                    {
                        "run_id": run_id,
                        "event_id": event_id,
                        "object_lane": "objects",
                        "object_order": object_order,
                    },
                    {"resolver_hints": obj.get("resolver_hints")},
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
                None,
                _normalize_str(step_neg.get("kind")),
                _normalize_str(step_neg.get("scope")),
                _normalize_str(step_neg.get("source")),
                _normalize_str(step.get("purpose")),
                _normalize_bool(step.get("claim_bearing")),
                None,
            ),
        )
        if step.get("action_meta") is not None:
            _insert_path_rows(
                conn,
                "wiki_timeline_step_field_values",
                {"run_id": run_id, "event_id": event_id, "step_index": step_index},
                {"action_meta": step.get("action_meta")},
            )
        if step_copy:
            _insert_path_rows(
                conn,
                "wiki_timeline_step_field_values",
                {"run_id": run_id, "event_id": event_id, "step_index": step_index},
                step_copy,
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
    _insert_run_list_rows(conn, run_id, "propositions", out_payload.get("propositions"))
    _insert_run_list_rows(conn, run_id, "proposition_links", out_payload.get("proposition_links"))


def _load_event_from_normalized(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    event: dict[str, Any] = {}
    event_field_value = _field_rows_to_value(
        conn,
        """
        SELECT path, value_type, value_text
        FROM wiki_timeline_event_field_values
        WHERE run_id = ? AND event_id = ?
        ORDER BY path
        """,
        (row["run_id"], row["event_id"]),
    )
    if isinstance(event_field_value, dict):
        event.update(event_field_value)
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
        SELECT object_lane, title, source, object_order
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
            object_field_value = _field_rows_to_value(
                conn,
                """
                SELECT path, value_type, value_text
                FROM wiki_timeline_event_object_field_values
                WHERE run_id = ? AND event_id = ? AND object_lane = ? AND object_order = ?
                ORDER BY path
                """,
                (row["run_id"], row["event_id"], lane, obj["object_order"]),
            )
            if isinstance(object_field_value, dict):
                entry.update(object_field_value)
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
            step_field_value = _field_rows_to_value(
                conn,
                """
                SELECT path, value_type, value_text
                FROM wiki_timeline_step_field_values
                WHERE run_id = ? AND event_id = ? AND step_index = ?
                ORDER BY path
                """,
                (row["run_id"], row["event_id"], step["step_index"]),
            )
            if isinstance(step_field_value, dict):
                step_payload.update(step_field_value)
            if step["action_id"] is not None:
                action_row = conn.execute("SELECT lemma FROM wiki_timeline_actions WHERE action_id = ?", (step["action_id"],)).fetchone()
                step_payload["action"] = action_row["lemma"] if action_row else None
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
        SELECT list_name, item_order, path, value_type, value_text
        FROM wiki_timeline_event_list_field_values
        WHERE run_id = ? AND event_id = ?
        ORDER BY list_name, item_order, path
        """,
        (row["run_id"], row["event_id"]),
    ).fetchall()
    if list_rows:
        grouped: dict[str, dict[int, list[tuple[str, str, str]]]] = {}
        for item in list_rows:
            grouped.setdefault(str(item["list_name"]), {}).setdefault(
                int(item["item_order"]), []
            ).append((str(item["path"]), str(item["value_type"]), str(item["value_text"])))
        event.update(
            {
                list_name: [_materialize_path_rows(items[index]) for index in sorted(items)]
                for list_name, items in grouped.items()
            }
        )

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
        SELECT list_name, item_order, path, value_type, value_text
        FROM wiki_timeline_run_list_field_values
        WHERE run_id = ?
        ORDER BY list_name, item_order, path
        """,
        (run_id,),
    ).fetchall()
    if run_list_rows:
        grouped: dict[str, dict[int, list[tuple[str, str, str]]]] = {}
        for item in run_list_rows:
            grouped.setdefault(str(item["list_name"]), {}).setdefault(
                int(item["item_order"]), []
            ).append((str(item["path"]), str(item["value_type"]), str(item["value_text"])))
        payload.update(
            {
                list_name: [_materialize_path_rows(items[index]) for index in sorted(items)]
                for list_name, items in grouped.items()
            }
        )

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
            INSERT INTO wiki_timeline_aoo_runs(
              run_id, generated_at,
              timeline_path, timeline_sha256,
              candidates_path, candidates_sha256,
              profile_path, profile_sha256,
              parser_json, parser_signature_sha256,
              extractor_sha256,
              out_meta_json, n_events
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id) DO UPDATE SET
              generated_at=excluded.generated_at,
              timeline_path=excluded.timeline_path,
              timeline_sha256=excluded.timeline_sha256,
              candidates_path=excluded.candidates_path,
              candidates_sha256=excluded.candidates_sha256,
              profile_path=excluded.profile_path,
              profile_sha256=excluded.profile_sha256,
              parser_json=excluded.parser_json,
              parser_signature_sha256=excluded.parser_signature_sha256,
              extractor_sha256=excluded.extractor_sha256,
              out_meta_json=excluded.out_meta_json,
              n_events=excluded.n_events
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
