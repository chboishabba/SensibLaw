#!/usr/bin/env python3
"""Upsert a minimal actor row into a SensibLaw ontology SQLite DB.

This is a curation-time helper to avoid manual sqlite fiddling when creating
root actors for external-linking work (e.g., DBpedia/Wikidata external refs).

Notes:
- The ontology schema does not enforce uniqueness on (kind, label), so this
  script implements a conservative "lookup then insert" behavior.
- It does not attempt to infer person/org details; those can be added later via
  direct SQL or a dedicated curator tool.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Optional


def _ensure_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def _find_actor_id(conn: sqlite3.Connection, *, kind: str, label: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM actors WHERE kind = ? AND label = ? ORDER BY id LIMIT 1",
        (kind, label),
    ).fetchone()
    if not row:
        return None
    return int(row[0])


def _insert_actor(conn: sqlite3.Connection, *, kind: str, label: str) -> int:
    cur = conn.execute("INSERT INTO actors (kind, label) VALUES (?, ?)", (kind, label))
    conn.commit()
    return int(cur.lastrowid)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--db",
        type=Path,
        default=Path("SensibLaw/.cache_local/sensiblaw_ontology.sqlite"),
        help="Path to ontology SQLite DB",
    )
    p.add_argument("--kind", default="person", help="Actor kind (e.g., person, organisation, place)")
    p.add_argument("--label", required=True, help="Canonical label (exact match)")
    p.add_argument("--dry-run", action="store_true", help="Report what would happen without inserting")
    args = p.parse_args()

    db_path: Path = args.db
    kind = str(args.kind).strip()
    label = str(args.label).strip()
    if not kind or not label:
        raise SystemExit("--kind and --label are required")

    conn = _ensure_db(db_path)
    try:
        existing = _find_actor_id(conn, kind=kind, label=label)
        if existing is not None:
            print(json.dumps({"ok": True, "db": str(db_path), "actor_id": existing, "created": False}, indent=2))
            return 0

        if args.dry_run:
            print(
                json.dumps(
                    {"ok": True, "db": str(db_path), "actor_id": None, "created": False, "would_create": True},
                    indent=2,
                )
            )
            return 0

        actor_id = _insert_actor(conn, kind=kind, label=label)
        print(json.dumps({"ok": True, "db": str(db_path), "actor_id": actor_id, "created": True}, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

