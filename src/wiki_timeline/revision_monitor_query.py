from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from src.wiki_timeline.revision_monitor_read_models import (
    changed_article_rows,
    contested_graph_payload,
    issue_packet_rows,
    latest_run_rows,
    selected_pair_rows,
    summary_from_read_models,
)


def repo_root_from_db(db_path: Path) -> Path:
    resolved = db_path.expanduser().resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "SensibLaw").exists():
            return parent
    return resolved.parents[2]


def manifest_pack_rows(repo_root: Path) -> list[dict[str, Any]]:
    pack_dir = repo_root / "SensibLaw" / "data" / "source_packs"
    rows: list[dict[str, Any]] = []
    if not pack_dir.exists():
        return rows
    for manifest_path in sorted(pack_dir.glob("wiki_revision_*.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        pack_id = str(payload.get("pack_id") or "").strip()
        if not pack_id:
            continue
        rows.append(
            {
                "pack_id": pack_id,
                "version": int(payload.get("version") or 0),
                "scope": str(payload.get("scope") or ""),
                "graph_enabled": bool(payload.get("graph_enabled")),
                "manifest_path": str(manifest_path),
                "updated_at": datetime.fromtimestamp(manifest_path.stat().st_mtime, UTC).isoformat(),
            }
        )
    return rows


def normalize_pack_rows(db_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in db_rows:
        merged[row["pack_id"]] = dict(row)
    for row in manifest_rows:
        pack_id = row["pack_id"]
        existing = merged.get(pack_id)
        if existing is None:
            merged[pack_id] = dict(row)
            continue
        existing.setdefault("manifest_path", row["manifest_path"])
        if not existing.get("scope"):
            existing["scope"] = row["scope"]
        if not existing.get("version"):
            existing["version"] = row["version"]
        if "graph_enabled" not in existing:
            existing["graph_enabled"] = row["graph_enabled"]
        if not existing.get("updated_at"):
            existing["updated_at"] = row["updated_at"]
    out = list(merged.values())
    out.sort(key=lambda row: str(row["pack_id"]))
    return out


def build_query_payload(*, db_path: Path, pack_id: str | None = None, run_id: str | None = None, article_id: str | None = None) -> dict[str, Any]:
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")

    repo_root = repo_root_from_db(db_path)
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = {row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        db_packs = [
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
        packs = normalize_pack_rows(db_packs, manifest_pack_rows(repo_root))
        pack_ids = {row["pack_id"] for row in packs}
        selected_pack = pack_id or (packs[0]["pack_id"] if packs else None)
        if selected_pack and selected_pack not in pack_ids:
            selected_pack = packs[0]["pack_id"] if packs else None

        db_runs: list[dict[str, Any]] = []
        if selected_pack:
            if "wiki_revision_monitor_run_summaries" in tables:
                db_runs = latest_run_rows(con, pack_id=selected_pack)
            else:
                db_runs = [
                    {
                        "run_id": row["run_id"],
                        "pack_id": row["pack_id"],
                        "started_at": row["started_at"],
                        "completed_at": row["completed_at"],
                        "status": row["status"],
                    }
                    for row in con.execute(
                        """
                SELECT run_id, pack_id, started_at, completed_at, status
                        FROM wiki_revision_monitor_runs
                        WHERE pack_id = ?
                        ORDER BY started_at DESC
                        """,
                        (selected_pack,),
                    ).fetchall()
                ]
        runs = list(db_runs)

        selected_run = run_id or (runs[0]["run_id"] if runs else None)
        summary = None
        summary_source = "none"
        if selected_run:
            if "wiki_revision_monitor_run_summaries" in tables and "wiki_revision_monitor_changed_articles" in tables:
                summary = summary_from_read_models(con, run_id=selected_run)
                if summary is not None:
                    summary_source = "sqlite_read_model"

        changed_articles = []
        if selected_run and "wiki_revision_monitor_changed_articles" in tables:
            changed_articles = changed_article_rows(con, run_id=selected_run)

        selected_article = article_id
        if not selected_article and changed_articles:
            selected_article = str(changed_articles[0].get("article_id") or "")
        if not selected_article and isinstance(summary, dict):
            articles = summary.get("articles") or []
            if isinstance(articles, list) and articles:
                selected_article = str(articles[0].get("article_id") or "")

        graph_payload = None
        selected_graph_source = "none"
        if selected_run and selected_article and "wiki_revision_monitor_contested_graphs" in tables:
            graph_payload = contested_graph_payload(con, run_id=selected_run, article_id=selected_article)
            if graph_payload is not None:
                selected_graph_source = "sqlite_read_model"

        selected_issue_packets = []
        if selected_run and selected_article and "wiki_revision_monitor_issue_packets" in tables:
            selected_issue_packets = issue_packet_rows(con, run_id=selected_run, article_id=selected_article)
        selected_pairs = []
        if selected_run and selected_article and "wiki_revision_monitor_selected_pairs" in tables:
            selected_pairs = selected_pair_rows(con, run_id=selected_run, article_id=selected_article)

        return {
            "db_path": str(db_path),
            "packs": packs,
            "selected_pack_id": selected_pack,
            "runs": runs,
            "latest_runs": db_runs,
            "selected_run_id": selected_run,
            "summary": summary,
            "summary_source": summary_source,
            "changed_articles": changed_articles,
            "selected_article_id": selected_article,
            "selected_pairs": selected_pairs,
            "selected_issue_packets": selected_issue_packets,
            "selected_graph": graph_payload,
            "selected_graph_source": selected_graph_source,
        }
    finally:
        con.close()
