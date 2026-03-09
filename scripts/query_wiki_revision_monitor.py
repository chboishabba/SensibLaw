#!/usr/bin/env python3
"""Query bounded wiki revision monitor runs and contested-region graph artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping


RUN_ID_RE = re.compile(r"^run:(?P<pack_id>[^:]+):(?P<started_at>.+):(?P<suffix>[^:]+)$")


def _read_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root_from_db(db_path: Path) -> Path:
    resolved = db_path.expanduser().resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "SensibLaw").exists():
            return parent
    return resolved.parents[2]


def _manifest_pack_rows(repo_root: Path) -> list[dict[str, Any]]:
    pack_dir = repo_root / "SensibLaw" / "data" / "source_packs"
    rows: list[dict[str, Any]] = []
    if not pack_dir.exists():
        return rows
    for manifest_path in sorted(pack_dir.glob("wiki_revision_*.json")):
        payload = _read_json(manifest_path)
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


def _normalize_pack_rows(db_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _parse_run_id(run_id: str) -> tuple[str | None, str | None]:
    m = RUN_ID_RE.match(run_id.strip())
    if not m:
        return None, None
    return m.group("pack_id"), m.group("started_at")


def _artifact_run_rows(repo_root: Path, pack_id: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    out_dir = repo_root / "SensibLaw" / "demo" / "ingest" / "wiki_revision_monitor" / pack_id
    graph_dir = out_dir / "contested_graphs"
    grouped: dict[str, list[dict[str, Any]]] = {}
    if graph_dir.exists():
        for graph_path in sorted(graph_dir.glob("*__run_*.json")):
            payload = _read_json(graph_path)
            if not isinstance(payload, Mapping):
                continue
            run = payload.get("run") if isinstance(payload.get("run"), Mapping) else {}
            article = payload.get("article") if isinstance(payload.get("article"), Mapping) else {}
            summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
            run_id = str(run.get("run_id") or "").strip()
            article_id = str(article.get("article_id") or "").strip()
            if not run_id or not article_id:
                continue
            grouped.setdefault(run_id, []).append(
                {
                    "article_id": article_id,
                    "title": str(article.get("title") or article_id),
                    "wiki": str(article.get("wiki") or ""),
                    "graph_path": str(graph_path),
                    "graph_payload": payload,
                    "summary": dict(summary),
                }
            )
    run_rows: list[dict[str, Any]] = []
    for run_id, rows in grouped.items():
        _, started_at = _parse_run_id(run_id)
        graph_mtimes = [Path(row["graph_path"]).stat().st_mtime for row in rows if Path(row["graph_path"]).exists()]
        completed_at = None
        if graph_mtimes:
            completed_at = max(graph_mtimes)
        run_rows.append(
            {
                "run_id": run_id,
                "pack_id": pack_id,
                "started_at": started_at,
                "completed_at": datetime.fromtimestamp(completed_at, UTC).isoformat() if completed_at else None,
                "status": "ok",
                "out_dir": str(out_dir),
            }
        )
    run_rows.sort(key=lambda row: str(row.get("started_at") or ""), reverse=True)
    return run_rows, grouped


def _severity_rank(value: str | None) -> int:
    s = str(value or "none").lower()
    if s == "high":
        return 3
    if s == "medium":
        return 2
    if s == "low":
        return 1
    return 0


def _highest_severity(values: list[str]) -> str:
    best = "none"
    for value in values:
        if _severity_rank(value) > _severity_rank(best):
            best = value
    return best


def _summary_from_graph_rows(pack_id: str, run_id: str, out_dir: str, graph_rows: list[dict[str, Any]]) -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    top_regions: list[dict[str, Any]] = []
    top_cycles: list[dict[str, Any]] = []
    top_pairs: list[dict[str, Any]] = []
    graph_count = 0
    region_total = 0
    cycle_total = 0
    highest_values: list[str] = []
    for row in graph_rows:
        payload = row["graph_payload"]
        summary = dict(row["summary"])
        selected_pairs = [dict(item) for item in (payload.get("selected_pairs") or []) if isinstance(item, Mapping)]
        for pair in selected_pairs:
            pair["article_id"] = row["article_id"]
        primary_pair = selected_pairs[0] if selected_pairs else {}
        article_payload = {
            "article_id": row["article_id"],
            "title": row["title"],
            "status": "changed",
            "top_severity": str(summary.get("highest_severity") or "none"),
            "report_path": primary_pair.get("pair_report_path"),
            "pair_reports": selected_pairs,
            "selected_pair_ids": [str(item.get("pair_id")) for item in selected_pairs if item.get("pair_id")],
            "selected_primary_pair_id": primary_pair.get("pair_id"),
            "selected_primary_pair_kind": primary_pair.get("pair_kind"),
            "selected_primary_pair_kinds": list(primary_pair.get("pair_kinds") or []),
            "selected_primary_pair_score": primary_pair.get("candidate_score"),
            "contested_graph_available": True,
            "contested_graph_path": row["graph_path"],
            "contested_graph_summary": summary,
        }
        articles.append(article_payload)
        graph_count += 1
        region_total += int(summary.get("region_count") or 0)
        cycle_total += int(summary.get("cycle_count") or 0)
        highest_values.append(str(summary.get("highest_severity") or "none"))
        hottest = summary.get("hottest_region")
        if isinstance(hottest, Mapping):
            top_regions.append(
                {
                    "article_id": row["article_id"],
                    "region_title": str(hottest.get("title") or hottest.get("region_id") or "(region)"),
                    "highest_severity": str(hottest.get("highest_severity") or "none"),
                    "touch_count": int(hottest.get("touch_count") or 0),
                    "total_touched_bytes": int(hottest.get("total_touched_bytes") or 0),
                }
            )
        for cycle in payload.get("cycles") or []:
            if isinstance(cycle, Mapping):
                top_cycles.append(
                    {
                        "article_id": row["article_id"],
                        "region_title": str(cycle.get("region_title") or cycle.get("region_id") or "(region)"),
                        "highest_severity": str(cycle.get("highest_severity") or "none"),
                        "touch_count": int(cycle.get("touch_count") or 0),
                        "reason": str(cycle.get("reason") or ""),
                    }
                )
        for region in payload.get("regions") or []:
            if isinstance(region, Mapping):
                top_regions.append(
                    {
                        "article_id": row["article_id"],
                        "region_title": str(region.get("title") or region.get("region_id") or "(region)"),
                        "highest_severity": str(region.get("highest_severity") or "none"),
                        "touch_count": int(region.get("touch_count") or 0),
                        "total_touched_bytes": int(region.get("total_touched_bytes") or 0),
                    }
                )
        top_pairs.extend(selected_pairs)

    highest = _highest_severity(highest_values)
    articles.sort(key=lambda row: (-_severity_rank(str(row.get("top_severity") or "none")), str(row.get("article_id") or "")))
    top_graphs = [
        {
            "article_id": row["article_id"],
            "title": row["title"],
            "top_severity": row["top_severity"],
            "graph_heat": float((row.get("contested_graph_summary") or {}).get("graph_heat") or 0),
            "region_count": int((row.get("contested_graph_summary") or {}).get("region_count") or 0),
            "cycle_count": int((row.get("contested_graph_summary") or {}).get("cycle_count") or 0),
        }
        for row in articles
    ]
    top_graphs.sort(key=lambda row: (-float(row.get("graph_heat") or 0), -_severity_rank(str(row.get("top_severity") or "none"))))
    top_regions.sort(key=lambda row: (-int(row.get("total_touched_bytes") or 0), -_severity_rank(str(row.get("highest_severity") or "none"))))
    top_cycles.sort(key=lambda row: (-int(row.get("touch_count") or 0), -_severity_rank(str(row.get("highest_severity") or "none"))))
    top_pairs.sort(key=lambda row: (-_severity_rank(str(row.get("top_severity") or "none")), -float(row.get("candidate_score") or 0)))

    return {
        "ok": True,
        "pack_id": pack_id,
        "run_id": run_id,
        "out_dir": out_dir,
        "schema_version": "wiki_revision_pack_state_v0_1",
        "counts": {
            "baseline_initialized": 0,
            "changed": len(articles),
            "error": 0,
            "unchanged": 0,
        },
        "highest_severity": highest,
        "contested_graph_counts": {
            "articles_with_graphs": graph_count,
            "graphs_built": graph_count,
            "cycles_detected": cycle_total,
            "regions_detected": region_total,
        },
        "pack_triage": {
            "top_contested_graphs": top_graphs[:5],
            "top_contested_cycles": top_cycles[:8],
            "top_contested_regions": top_regions[:10],
            "top_high_severity_pairs": top_pairs[:8],
        },
        "articles": articles,
    }


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

    repo_root = _repo_root_from_db(db_path)
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    con.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
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
        packs = _normalize_pack_rows(db_packs, _manifest_pack_rows(repo_root))
        pack_ids = {row["pack_id"] for row in packs}
        selected_pack = args.pack_id or (packs[0]["pack_id"] if packs else None)
        if selected_pack and selected_pack not in pack_ids:
            selected_pack = packs[0]["pack_id"] if packs else None

        db_runs: list[dict[str, Any]] = []
        if selected_pack:
            db_runs = [
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
        artifact_runs, artifact_graphs = _artifact_run_rows(repo_root, selected_pack) if selected_pack else ([], {})
        run_map: dict[str, dict[str, Any]] = {row["run_id"]: dict(row) for row in db_runs}
        for row in artifact_runs:
            run_map.setdefault(row["run_id"], dict(row))
        runs = list(run_map.values())
        runs.sort(key=lambda row: str(row.get("started_at") or ""), reverse=True)

        selected_run = args.run_id or (runs[0]["run_id"] if runs else None)
        summary = None
        selected_run_row = run_map.get(selected_run or "")
        if selected_run:
            row = con.execute(
                "SELECT summary_json FROM wiki_revision_monitor_runs WHERE run_id = ?",
                (selected_run,),
            ).fetchone()
            if row and row["summary_json"]:
                summary = json.loads(row["summary_json"])
            elif selected_pack and selected_run in artifact_graphs:
                out_dir = str((repo_root / "SensibLaw" / "demo" / "ingest" / "wiki_revision_monitor" / selected_pack))
                summary = _summary_from_graph_rows(selected_pack, selected_run, out_dir, artifact_graphs[selected_run])

        selected_article = args.article_id
        if not selected_article and isinstance(summary, dict):
            articles = summary.get("articles") or []
            if isinstance(articles, list) and articles:
                selected_article = str(articles[0].get("article_id") or "")

        graph_payload = None
        if selected_run and selected_article and "wiki_revision_monitor_contested_graphs" in tables:
            row = con.execute(
                """
                SELECT graph_json, graph_path
                FROM wiki_revision_monitor_contested_graphs
                WHERE run_id = ? AND article_id = ?
                """,
                (selected_run, selected_article),
            ).fetchone()
            if row:
                if row["graph_json"]:
                    graph_payload = json.loads(row["graph_json"])
                elif row["graph_path"]:
                    graph_payload = _read_json(Path(row["graph_path"]))

        if graph_payload is None and isinstance(summary, dict) and selected_article:
            article_rows = summary.get("articles") or []
            selected_article_row = next(
                (row for row in article_rows if isinstance(row, Mapping) and str(row.get("article_id") or "") == selected_article),
                None,
            )
            if isinstance(selected_article_row, Mapping):
                graph_path = selected_article_row.get("contested_graph_path")
                if graph_path:
                    graph_payload = _read_json(Path(str(graph_path)))

        if graph_payload is None and selected_run and selected_run in artifact_graphs and selected_article:
            for row in artifact_graphs[selected_run]:
                if row["article_id"] == selected_article:
                    graph_payload = row["graph_payload"]
                    break

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
