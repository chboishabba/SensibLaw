#!/usr/bin/env python3
"""Query bounded wiki revision monitor runs and contested-region graph artifacts."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Query wiki revision monitor runs and contested-region graph artifacts.")
    ap.add_argument("--db-path", required=True)
    ap.add_argument("--pack-id", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--article-id", default=None)
    args = ap.parse_args(argv)

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        packs = [
            {
                "pack_id": row["pack_id"],
                "version": row["version"],
                "scope": row["scope"],
                "manifest_path": row["manifest_path"],
                "updated_at": row["updated_at"],
            }
            for row in con.execute(
                """
                SELECT pack_id, version, scope, manifest_path, updated_at
                FROM wiki_revision_monitor_packs
                ORDER BY pack_id
                """
            ).fetchall()
        ]
        pack_ids = {row["pack_id"] for row in packs}
        selected_pack = args.pack_id or (packs[0]["pack_id"] if packs else None)
        if selected_pack and selected_pack not in pack_ids:
            selected_pack = packs[0]["pack_id"] if packs else None
        runs = []
        if selected_pack:
            runs = [
                {
                    "run_id": row["run_id"],
                    "pack_id": row["pack_id"],
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "status": row["status"],
                    "out_dir": row["out_dir"],
                }
                for row in con.execute(
                    """
                    SELECT run_id, pack_id, started_at, completed_at, status, out_dir
                    FROM wiki_revision_monitor_runs
                    WHERE pack_id = ?
                    ORDER BY started_at DESC
                    """,
                    (selected_pack,),
                ).fetchall()
            ]
        selected_run = args.run_id or (runs[0]["run_id"] if runs else None)
        summary = None
        if selected_run:
            row = con.execute(
                "SELECT summary_json FROM wiki_revision_monitor_runs WHERE run_id = ?",
                (selected_run,),
            ).fetchone()
            if row and row["summary_json"]:
                summary = json.loads(row["summary_json"])
        selected_article = args.article_id
        if not selected_article and isinstance(summary, dict):
            articles = summary.get("articles") or []
            if isinstance(articles, list) and articles:
                selected_article = str(articles[0].get("article_id") or "")
        graph_payload = None
        if selected_run and selected_article and "wiki_revision_monitor_contested_graphs" in tables:
            row = con.execute(
                """
                SELECT graph_path
                FROM wiki_revision_monitor_contested_graphs
                WHERE run_id = ? AND article_id = ?
                """,
                (selected_run, selected_article),
            ).fetchone()
            if row and row["graph_path"]:
                graph_payload = _read_json(Path(row["graph_path"]))

        payload = {
            "db_path": str(db_path),
            "packs": packs,
            "selected_pack_id": selected_pack,
            "runs": runs,
            "selected_run_id": selected_run,
            "summary": summary,
            "selected_article_id": selected_article,
            "selected_graph": graph_payload,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        con.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
