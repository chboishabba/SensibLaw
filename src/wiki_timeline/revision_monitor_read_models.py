from __future__ import annotations

import sqlite3
from typing import Any, Mapping
import json

from src.wiki_timeline.revision_pack_summary import severity_rank


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(row[1]) for row in rows]


def _needs_rebuild(conn: sqlite3.Connection, *, table_name: str, target_columns: list[str]) -> bool:
    existing = _table_columns(conn, table_name)
    return bool(existing) and existing != target_columns


def _snapshot_rows(conn: sqlite3.Connection, *, table_name: str, columns: list[str]) -> list[tuple[Any, ...]]:
    existing = _table_columns(conn, table_name)
    if not existing:
        return []
    selected = [column for column in columns if column in existing]
    if not selected:
        return []
    return conn.execute(f"SELECT {', '.join(selected)} FROM {table_name}").fetchall()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def ensure_read_model_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_run_summaries (
          run_id TEXT PRIMARY KEY REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          status TEXT NOT NULL,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          baseline_initialized_count INTEGER NOT NULL DEFAULT 0,
          unchanged_count INTEGER NOT NULL DEFAULT 0,
          changed_count INTEGER NOT NULL DEFAULT 0,
          error_count INTEGER NOT NULL DEFAULT 0,
          no_candidate_delta_count INTEGER NOT NULL DEFAULT 0,
          candidate_considered_count INTEGER NOT NULL DEFAULT 0,
          candidate_selected_count INTEGER NOT NULL DEFAULT 0,
          candidate_reported_count INTEGER NOT NULL DEFAULT 0,
          graphs_article_count INTEGER NOT NULL DEFAULT 0,
          graphs_built_count INTEGER NOT NULL DEFAULT 0,
          regions_detected_count INTEGER NOT NULL DEFAULT 0,
          cycles_detected_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_changed_articles (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
          title TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          top_severity TEXT NOT NULL DEFAULT 'none',
          previous_revid INTEGER,
          current_revid INTEGER,
          selected_primary_pair_id TEXT,
          selected_primary_pair_kind TEXT,
          selected_primary_pair_score REAL NOT NULL DEFAULT 0,
          candidate_pairs_selected INTEGER NOT NULL DEFAULT 0,
          contested_graph_available INTEGER NOT NULL DEFAULT 0,
          contested_region_count INTEGER NOT NULL DEFAULT 0,
          contested_cycle_count INTEGER NOT NULL DEFAULT 0,
          graph_heat REAL NOT NULL DEFAULT 0,
          PRIMARY KEY (run_id, article_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_issue_packets (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          pair_id TEXT NOT NULL,
          packet_id TEXT NOT NULL,
          packet_order INTEGER NOT NULL,
          severity TEXT NOT NULL DEFAULT 'low',
          summary TEXT,
          event_id TEXT,
          surfaces_json TEXT NOT NULL,
          related_entities_json TEXT NOT NULL,
          state_change_summary_json TEXT NOT NULL,
          review_context_json TEXT,
          packet_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, pair_id, packet_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_selected_pairs (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          pair_id TEXT NOT NULL,
          pair_kind TEXT NOT NULL,
          pair_kinds_json TEXT NOT NULL,
          older_revid INTEGER,
          newer_revid INTEGER,
          candidate_score REAL NOT NULL DEFAULT 0,
          top_severity TEXT NOT NULL DEFAULT 'none',
          top_changed_sections_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, pair_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_events (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          event_id TEXT NOT NULL,
          event_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_epistemic (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          epistemic_id TEXT NOT NULL,
          epistemic_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, epistemic_id)
        )
        """
    )


    rebuild_specs = [
        (
            "wiki_revision_monitor_changed_articles",
            [
                "run_id",
                "article_id",
                "pack_id",
                "title",
                "status",
                "top_severity",
                "previous_revid",
                "current_revid",
                "selected_primary_pair_id",
                "selected_primary_pair_kind",
                "selected_primary_pair_score",
                "candidate_pairs_selected",
                "contested_graph_available",
                "contested_region_count",
                "contested_cycle_count",
                "graph_heat",
            ],
        ),
        (
            "wiki_revision_monitor_selected_pairs",
            [
                "run_id",
                "article_id",
                "pair_id",
                "pair_kind",
                "pair_kinds_json",
                "older_revid",
                "newer_revid",
                "candidate_score",
                "top_severity",
                "top_changed_sections_json",
            ],
        ),
    ]
    if any(_needs_rebuild(conn, table_name=table_name, target_columns=target_columns) for table_name, target_columns in rebuild_specs):
        changed_rows = _snapshot_rows(
            conn,
            table_name="wiki_revision_monitor_changed_articles",
            columns=[
                "run_id", "article_id", "pack_id", "title", "status", "top_severity",
                "previous_revid", "current_revid", "selected_primary_pair_id",
                "selected_primary_pair_kind", "selected_primary_pair_score",
                "candidate_pairs_selected", "contested_graph_available",
                "contested_region_count", "contested_cycle_count", "graph_heat",
            ],
        )
        pair_rows = _snapshot_rows(
            conn,
            table_name="wiki_revision_monitor_selected_pairs",
            columns=[
                "run_id", "article_id", "pair_id", "pair_kind", "pair_kinds_json",
                "older_revid", "newer_revid", "candidate_score", "top_severity",
                "top_changed_sections_json",
            ],
        )
        conn.execute("PRAGMA foreign_keys = OFF")
        for table_name in ["wiki_revision_monitor_selected_pairs", "wiki_revision_monitor_changed_articles"]:
            if _table_columns(conn, table_name):
                conn.execute(f"DROP TABLE {table_name}")
        conn.execute(
            """
            CREATE TABLE wiki_revision_monitor_changed_articles (
              run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
              article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
              pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
              title TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL,
              top_severity TEXT NOT NULL DEFAULT 'none',
              previous_revid INTEGER,
              current_revid INTEGER,
              selected_primary_pair_id TEXT,
              selected_primary_pair_kind TEXT,
              selected_primary_pair_score REAL NOT NULL DEFAULT 0,
              candidate_pairs_selected INTEGER NOT NULL DEFAULT 0,
              contested_graph_available INTEGER NOT NULL DEFAULT 0,
              contested_region_count INTEGER NOT NULL DEFAULT 0,
              contested_cycle_count INTEGER NOT NULL DEFAULT 0,
              graph_heat REAL NOT NULL DEFAULT 0,
              PRIMARY KEY (run_id, article_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE wiki_revision_monitor_selected_pairs (
              run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
              article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
              pair_id TEXT NOT NULL,
              pair_kind TEXT NOT NULL,
              pair_kinds_json TEXT NOT NULL,
              older_revid INTEGER,
              newer_revid INTEGER,
              candidate_score REAL NOT NULL DEFAULT 0,
              top_severity TEXT NOT NULL DEFAULT 'none',
              top_changed_sections_json TEXT NOT NULL,
              PRIMARY KEY (run_id, article_id, pair_id)
            )
            """
        )
        if changed_rows:
            conn.executemany(
                """
                INSERT INTO wiki_revision_monitor_changed_articles(
                  run_id, article_id, pack_id, title, status, top_severity, previous_revid, current_revid,
                  selected_primary_pair_id, selected_primary_pair_kind, selected_primary_pair_score,
                  candidate_pairs_selected, contested_graph_available, contested_region_count,
                  contested_cycle_count, graph_heat
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                changed_rows,
            )
        if pair_rows:
            conn.executemany(
                """
                INSERT INTO wiki_revision_monitor_selected_pairs(
                  run_id, article_id, pair_id, pair_kind, pair_kinds_json, older_revid, newer_revid,
                  candidate_score, top_severity, top_changed_sections_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                pair_rows,
            )
        conn.execute("PRAGMA foreign_keys = ON")


def upsert_run_summary(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    pack_id: str,
    started_at: str,
    completed_at: str | None,
    status: str,
    summary: Mapping[str, Any],
) -> None:
    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    pair_counts = summary.get("candidate_pair_counts") if isinstance(summary.get("candidate_pair_counts"), Mapping) else {}
    graph_counts = summary.get("contested_graph_counts") if isinstance(summary.get("contested_graph_counts"), Mapping) else {}
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_run_summaries(
          run_id, pack_id, started_at, completed_at, status, highest_severity,
          baseline_initialized_count, unchanged_count, changed_count, error_count, no_candidate_delta_count,
          candidate_considered_count, candidate_selected_count, candidate_reported_count,
          graphs_article_count, graphs_built_count, regions_detected_count, cycles_detected_count
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET
          pack_id=excluded.pack_id,
          started_at=excluded.started_at,
          completed_at=excluded.completed_at,
          status=excluded.status,
          highest_severity=excluded.highest_severity,
          baseline_initialized_count=excluded.baseline_initialized_count,
          unchanged_count=excluded.unchanged_count,
          changed_count=excluded.changed_count,
          error_count=excluded.error_count,
          no_candidate_delta_count=excluded.no_candidate_delta_count,
          candidate_considered_count=excluded.candidate_considered_count,
          candidate_selected_count=excluded.candidate_selected_count,
          candidate_reported_count=excluded.candidate_reported_count,
          graphs_article_count=excluded.graphs_article_count,
          graphs_built_count=excluded.graphs_built_count,
          regions_detected_count=excluded.regions_detected_count,
          cycles_detected_count=excluded.cycles_detected_count
        """,
        (
            run_id,
            pack_id,
            started_at,
            completed_at,
            status,
            str(summary.get("highest_severity") or "none"),
            _safe_int(counts.get("baseline_initialized")),
            _safe_int(counts.get("unchanged")),
            _safe_int(counts.get("changed")),
            _safe_int(counts.get("error")),
            _safe_int(counts.get("no_candidate_delta")),
            _safe_int(pair_counts.get("considered")),
            _safe_int(pair_counts.get("selected")),
            _safe_int(pair_counts.get("reported")),
            _safe_int(graph_counts.get("articles_with_graphs")),
            _safe_int(graph_counts.get("graphs_built")),
            _safe_int(graph_counts.get("regions_detected")),
            _safe_int(graph_counts.get("cycles_detected")),
        ),
    )


def replace_changed_articles(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    pack_id: str,
    article_rows: list[Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM wiki_revision_monitor_changed_articles WHERE run_id = ?", (run_id,))
    for row in article_rows:
        if not isinstance(row, Mapping):
            continue
        graph_summary = row.get("contested_graph_summary") if isinstance(row.get("contested_graph_summary"), Mapping) else {}
        conn.execute(
            """
            INSERT INTO wiki_revision_monitor_changed_articles(
              run_id, article_id, pack_id, title, status, top_severity, previous_revid, current_revid,
              selected_primary_pair_id, selected_primary_pair_kind, selected_primary_pair_score,
              candidate_pairs_selected, contested_graph_available, contested_region_count, contested_cycle_count, graph_heat
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                str(row.get("article_id") or ""),
                pack_id,
                str(row.get("title") or ""),
                str(row.get("status") or ""),
                str(row.get("top_severity") or "none"),
                row.get("previous_revid"),
                row.get("current_revid"),
                row.get("selected_primary_pair_id"),
                row.get("selected_primary_pair_kind"),
                _safe_float(row.get("selected_primary_pair_score")),
                _safe_int(row.get("candidate_pairs_selected")),
                1 if row.get("contested_graph_available") else 0,
                _safe_int(graph_summary.get("region_count")),
                _safe_int(graph_summary.get("cycle_count")),
                _safe_float(graph_summary.get("graph_heat")),
            ),
        )


def replace_issue_packets(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    packet_rows: list[Mapping[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM wiki_revision_monitor_issue_packets WHERE run_id = ? AND article_id = ?",
        (run_id, article_id),
    )
    for index, row in enumerate(packet_rows):
        if not isinstance(row, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO wiki_revision_monitor_issue_packets(
              run_id, article_id, pair_id, packet_id, packet_order, severity, summary, event_id,
              surfaces_json, related_entities_json, state_change_summary_json, review_context_json, packet_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(row.get("pair_id") or ""),
                str(row.get("packet_id") or ""),
                int(row.get("packet_order") if row.get("packet_order") is not None else index),
                str(row.get("severity") or "low"),
                row.get("summary"),
                row.get("event_id"),
                __import__("json").dumps(row.get("surfaces") or [], sort_keys=True),
                json.dumps(row.get("related_entities") or [], sort_keys=True),
                json.dumps(row.get("state_change_summary") or [], sort_keys=True),
                json.dumps(row.get("review_context"), sort_keys=True) if row.get("review_context") is not None else None,
                json.dumps(row, sort_keys=True),
            ),
        )


def replace_selected_pairs(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    pair_rows: list[Mapping[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM wiki_revision_monitor_selected_pairs WHERE run_id = ? AND article_id = ?",
        (run_id, article_id),
    )
    for row in pair_rows:
        if not isinstance(row, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO wiki_revision_monitor_selected_pairs(
              run_id, article_id, pair_id, pair_kind, pair_kinds_json, older_revid, newer_revid,
              candidate_score, top_severity, top_changed_sections_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(row.get("pair_id") or ""),
                str(row.get("pair_kind") or ""),
                json.dumps(row.get("pair_kinds") or [], sort_keys=True),
                row.get("older_revid"),
                row.get("newer_revid"),
                _safe_float(row.get("candidate_score")),
                str(row.get("top_severity") or "none"),
                json.dumps(row.get("top_changed_sections") or [], sort_keys=True),
            ),
        )


def latest_run_rows(conn: sqlite3.Connection, *, pack_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT run_id, pack_id, started_at, completed_at, status, highest_severity,
               changed_count, error_count, candidate_reported_count, graphs_built_count
        FROM wiki_revision_monitor_run_summaries
        WHERE pack_id = ?
        ORDER BY started_at DESC
        """,
        (pack_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def changed_article_rows(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT article_id, pack_id, title, status, top_severity, previous_revid, current_revid,
               selected_primary_pair_id, selected_primary_pair_kind, selected_primary_pair_score,
               candidate_pairs_selected, contested_graph_available, contested_region_count, contested_cycle_count, graph_heat
        FROM wiki_revision_monitor_changed_articles
        WHERE run_id = ?
        ORDER BY
          CASE top_severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
          selected_primary_pair_score DESC,
          candidate_pairs_selected DESC,
          article_id ASC
        """,
        (run_id,),
    ).fetchall()
    out = [dict(row) for row in rows]
    for row in out:
        row["contested_graph_available"] = bool(row.get("contested_graph_available"))
    return out


def issue_packet_rows(conn: sqlite3.Connection, *, run_id: str, article_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pair_id, packet_id, packet_order, severity, summary, event_id,
               surfaces_json, related_entities_json, state_change_summary_json, review_context_json, packet_json
        FROM wiki_revision_monitor_issue_packets
        WHERE run_id = ? AND article_id = ?
        ORDER BY
          CASE severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
          packet_order ASC,
          packet_id ASC
        """,
        (run_id, article_id),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["surfaces"] = json.loads(payload.pop("surfaces_json") or "[]")
        payload["related_entities"] = json.loads(payload.pop("related_entities_json") or "[]")
        payload["state_change_summary"] = json.loads(payload.pop("state_change_summary_json") or "[]")
        payload["review_context"] = json.loads(payload.pop("review_context_json")) if payload.get("review_context_json") else None
        payload["packet"] = json.loads(payload.pop("packet_json") or "{}")
        out.append(payload)
    return out


def selected_pair_rows(conn: sqlite3.Connection, *, run_id: str, article_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pair_id, pair_kind, pair_kinds_json, older_revid, newer_revid, candidate_score,
               top_severity, top_changed_sections_json
        FROM wiki_revision_monitor_selected_pairs
        WHERE run_id = ? AND article_id = ?
        ORDER BY
          CASE top_severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 WHEN 'low' THEN 1 ELSE 0 END DESC,
          candidate_score DESC,
          pair_id ASC
        """,
        (run_id, article_id),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["pair_kinds"] = json.loads(payload.pop("pair_kinds_json") or "[]")
        payload["top_changed_sections"] = json.loads(payload.pop("top_changed_sections_json") or "[]")
        out.append(payload)
    return out


def contested_graph_payload(conn: sqlite3.Connection, *, run_id: str, article_id: str) -> dict[str, Any] | None:
    graph_row = conn.execute(
        """
        SELECT region_count, cycle_count, selected_pair_count, changed_event_count,
               changed_attribution_count, highest_severity, hottest_region_json
        FROM wiki_revision_monitor_contested_graphs
        WHERE run_id = ? AND article_id = ?
        """,
        (run_id, article_id),
    ).fetchone()
    if graph_row is None:
        return None
    article_row = conn.execute(
        """
        SELECT title, wiki
        FROM wiki_revision_monitor_articles
        WHERE article_id = ?
        """,
        (article_id,),
    ).fetchone()
    regions = [
        json.loads(row["region_json"])
        for row in conn.execute(
            """
            SELECT region_json
            FROM wiki_revision_monitor_contested_regions
            WHERE run_id = ? AND article_id = ?
            ORDER BY highest_severity DESC, total_touched_bytes DESC, touch_count DESC, title ASC
            """,
            (run_id, article_id),
        ).fetchall()
        if row["region_json"]
    ]
    cycles = [
        json.loads(row["cycle_json"])
        for row in conn.execute(
            """
            SELECT cycle_json
            FROM wiki_revision_monitor_contested_cycles
            WHERE run_id = ? AND article_id = ?
            ORDER BY highest_severity DESC, touch_count DESC, cycle_id ASC
            """,
            (run_id, article_id),
        ).fetchall()
        if row["cycle_json"]
    ]
    edges = [
        json.loads(row["edge_json"])
        for row in conn.execute(
            """
            SELECT edge_json
            FROM wiki_revision_monitor_contested_edges
            WHERE run_id = ? AND article_id = ?
            ORDER BY edge_id ASC
            """,
            (run_id, article_id),
        ).fetchall()
        if row["edge_json"]
    ]
    events = [
        json.loads(row["event_json"])
        for row in conn.execute(
            """
            SELECT event_json
            FROM wiki_revision_monitor_contested_events
            WHERE run_id = ? AND article_id = ?
            ORDER BY event_id ASC
            """,
            (run_id, article_id),
        ).fetchall()
        if row["event_json"]
    ]
    epistemic_surfaces = [
        json.loads(row["epistemic_json"])
        for row in conn.execute(
            """
            SELECT epistemic_json
            FROM wiki_revision_monitor_contested_epistemic
            WHERE run_id = ? AND article_id = ?
            ORDER BY epistemic_id ASC
            """,
            (run_id, article_id),
        ).fetchall()
        if row["epistemic_json"]
    ]
    selected_pairs = selected_pair_rows(conn, run_id=run_id, article_id=article_id)
    hottest_region = json.loads(graph_row["hottest_region_json"]) if graph_row["hottest_region_json"] else None
    summary = {
        "region_count": graph_row["region_count"],
        "selected_pair_count": graph_row["selected_pair_count"],
        "changed_event_count": graph_row["changed_event_count"],
        "changed_attribution_count": graph_row["changed_attribution_count"],
        "cycle_count": graph_row["cycle_count"],
        "highest_severity": graph_row["highest_severity"],
        "partial": False,
        "graph_heat": round(sum(float(region.get("graph_heat") or 0.0) for region in regions), 3),
        "hottest_region": hottest_region,
        "top_regions": regions[:5],
        "top_cycles": cycles[:5],
    }
    return {
        "schema_version": "wiki_contested_region_graph_v0_1",
        "article": {
            "article_id": article_id,
            "title": article_row["title"] if article_row else article_id,
            "wiki": article_row["wiki"] if article_row else "enwiki",
        },
        "run": {"run_id": run_id},
        "regions": regions,
        "selected_pairs": selected_pairs,
        "events": events,
        "epistemic_surfaces": epistemic_surfaces,
        "edges": edges,
        "cycles": cycles,
        "summary": summary,
    }


def summary_from_read_models(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any] | None:
    run_row = conn.execute(
        """
        SELECT run_id, pack_id, started_at, completed_at, status, highest_severity,
               baseline_initialized_count, unchanged_count, changed_count, error_count, no_candidate_delta_count,
               candidate_considered_count, candidate_selected_count, candidate_reported_count,
               graphs_article_count, graphs_built_count, regions_detected_count, cycles_detected_count
        FROM wiki_revision_monitor_run_summaries
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        return None
    articles = changed_article_rows(conn, run_id=run_id)
    top_articles = [
        {
            "article_id": row["article_id"],
            "title": row.get("title"),
            "status": row.get("status"),
            "top_severity": row.get("top_severity"),
            "selected_primary_pair_id": row.get("selected_primary_pair_id"),
            "selected_primary_pair_kind": row.get("selected_primary_pair_kind"),
            "selected_primary_pair_score": row.get("selected_primary_pair_score"),
            "candidate_pairs_selected": row.get("candidate_pairs_selected"),
        }
        for row in articles
    ]
    top_articles.sort(
        key=lambda row: (
            -severity_rank(row.get("top_severity")),
            -_safe_float(row.get("selected_primary_pair_score")),
            -_safe_int(row.get("candidate_pairs_selected")),
            str(row.get("article_id") or ""),
        )
    )
    return {
        "ok": True,
        "pack_id": run_row["pack_id"],
        "run_id": run_row["run_id"],
        "counts": {
            "baseline_initialized": run_row["baseline_initialized_count"],
            "unchanged": run_row["unchanged_count"],
            "changed": run_row["changed_count"],
            "error": run_row["error_count"],
            "no_candidate_delta": run_row["no_candidate_delta_count"],
        },
        "candidate_pair_counts": {
            "considered": run_row["candidate_considered_count"],
            "selected": run_row["candidate_selected_count"],
            "reported": run_row["candidate_reported_count"],
        },
        "contested_graph_counts": {
            "articles_with_graphs": run_row["graphs_article_count"],
            "graphs_built": run_row["graphs_built_count"],
            "regions_detected": run_row["regions_detected_count"],
            "cycles_detected": run_row["cycles_detected_count"],
        },
        "highest_severity": run_row["highest_severity"],
        "pack_triage": {
            "top_changed_articles": top_articles[:5],
        },
        "articles": articles,
    }
