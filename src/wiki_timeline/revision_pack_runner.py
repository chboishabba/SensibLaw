from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from src.wiki_timeline.revision_harness import build_revision_comparison_report
from src.wiki_timeline.revision_pack_storage import (
    default_out_dir_for_pack,
    graph_artifact_path,
    pair_artifact_paths,
    read_json_file,
    revision_artifact_paths,
    slug_artifact_name,
    stable_json,
    write_json_file,
)
from src.wiki_timeline.revision_monitor_read_models import (
    ensure_read_model_schema,
    replace_changed_articles,
    replace_issue_packets,
    replace_selected_pairs,
    upsert_run_summary,
)
from src.wiki_timeline.revision_pack_summary import (
    build_run_summary,
    human_summary as _human_summary,
    severity_rank,
)

STATE_SCHEMA_VERSION = "wiki_revision_pack_state_v0_5"
PAIR_REPORT_SCHEMA_VERSION = "wiki_revision_pair_report_v0_1"
CONTESTED_GRAPH_SCHEMA_VERSION = "wiki_contested_region_graph_v0_1"
_WS_RE = re.compile(r"\s+")
_SECTION_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.MULTILINE)
_REVERT_RE = re.compile(r"\b(revert|reverted|reverting|undid|undo|rv|rollback)\b", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_text(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _emit_progress(progress_callback: Callable[[str, Mapping[str, Any]], None] | None, stage: str, details: Mapping[str, Any]) -> None:
    if callable(progress_callback):
        progress_callback(stage, dict(details))


def _snapshot_contract_error(article: Mapping[str, Any], snapshot_payload: Mapping[str, Any]) -> str | None:
    warnings = snapshot_payload.get("warnings") or []
    warning_text = ", ".join(str(item) for item in warnings if item)
    if snapshot_payload.get("revid") is None or not _norm_text(snapshot_payload.get("wikitext")):
        detail = f" ({warning_text})" if warning_text else ""
        return f"wiki pull returned incomplete snapshot for {article.get('title')}{detail}"
    return None


def _history_row_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return (_safe_int(row.get("revid")) or -1, str(row.get("timestamp") or ""))


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = _norm_text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _rebuild_table_with_columns(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    create_sql: str,
    target_columns: list[str],
) -> None:
    existing_columns = _table_columns(conn, table_name)
    if not existing_columns:
        return
    if existing_columns == set(target_columns):
        return
    temp_name = f"{table_name}__legacy_v0_3"
    shared_columns = [column for column in target_columns if column in existing_columns]
    conn.execute(f"ALTER TABLE {table_name} RENAME TO {temp_name}")
    conn.execute(create_sql)
    if shared_columns:
        column_list = ", ".join(shared_columns)
        conn.execute(
            f"INSERT INTO {table_name} ({column_list}) SELECT {column_list} FROM {temp_name}"
        )
    conn.execute(f"DROP TABLE {temp_name}")


ARTICLE_RESULTS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS wiki_revision_monitor_article_results (
  run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
  article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  previous_revid INTEGER,
  current_revid INTEGER,
  top_severity TEXT NOT NULL,
  snapshot_path TEXT,
  timeline_path TEXT,
  aoo_path TEXT,
  report_path TEXT,
  PRIMARY KEY (run_id, article_id)
)
"""


CANDIDATE_PAIRS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS wiki_revision_monitor_candidate_pairs (
  run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
  article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
  pair_id TEXT NOT NULL,
  pair_kind TEXT NOT NULL,
  older_revid INTEGER,
  newer_revid INTEGER,
  selected INTEGER NOT NULL DEFAULT 0,
  score REAL NOT NULL DEFAULT 0,
  pair_report_path TEXT,
  status TEXT NOT NULL,
  PRIMARY KEY (run_id, article_id, pair_id)
)
"""


RUNS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS wiki_revision_monitor_runs (
  run_id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  out_dir TEXT NOT NULL
)
"""


CONTESTED_GRAPHS_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_graphs (
  run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
  article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
  graph_path TEXT NOT NULL,
  region_count INTEGER NOT NULL DEFAULT 0,
  cycle_count INTEGER NOT NULL DEFAULT 0,
  selected_pair_count INTEGER NOT NULL DEFAULT 0,
  changed_event_count INTEGER NOT NULL DEFAULT 0,
  changed_attribution_count INTEGER NOT NULL DEFAULT 0,
  highest_severity TEXT NOT NULL DEFAULT 'none',
  hottest_region_json TEXT,
  PRIMARY KEY (run_id, article_id)
)
"""


def ensure_revision_pack_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_packs (
          pack_id TEXT PRIMARY KEY,
          version INTEGER,
          scope TEXT,
          manifest_path TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_articles (
          article_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
          wiki TEXT NOT NULL,
          title TEXT NOT NULL,
          role TEXT NOT NULL,
          topics_json TEXT NOT NULL,
          review_context_json TEXT NOT NULL,
          article_order INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_article_state (
          article_id TEXT PRIMARY KEY REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          last_revid INTEGER,
          last_rev_timestamp TEXT,
          last_fetched_at TEXT,
          snapshot_path TEXT,
          timeline_path TEXT,
          aoo_path TEXT,
          report_path TEXT,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(RUNS_CREATE_SQL)
    conn.execute(ARTICLE_RESULTS_CREATE_SQL)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_history_rows (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          row_order INTEGER NOT NULL,
          revid INTEGER,
          parentid INTEGER,
          timestamp TEXT,
          size INTEGER,
          comment TEXT,
          row_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, row_order)
        )
        """
    )
    conn.execute(CANDIDATE_PAIRS_CREATE_SQL)
    conn.execute(CONTESTED_GRAPHS_CREATE_SQL)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_regions (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          region_id TEXT NOT NULL,
          title TEXT NOT NULL,
          touch_count INTEGER NOT NULL DEFAULT 0,
          total_touched_bytes INTEGER NOT NULL DEFAULT 0,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          region_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, region_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_cycles (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          cycle_id TEXT NOT NULL,
          region_id TEXT NOT NULL,
          touch_count INTEGER NOT NULL DEFAULT 0,
          highest_severity TEXT NOT NULL DEFAULT 'none',
          cycle_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, cycle_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_contested_edges (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          edge_id TEXT NOT NULL,
          edge_kind TEXT NOT NULL,
          source_id TEXT NOT NULL,
          target_id TEXT NOT NULL,
          edge_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, edge_id)
        )
        """
    )
    _rebuild_table_with_columns(
        conn,
        table_name="wiki_revision_monitor_runs",
        create_sql=RUNS_CREATE_SQL,
        target_columns=[
            "run_id",
            "pack_id",
            "started_at",
            "completed_at",
            "status",
            "out_dir",
        ],
    )
    _rebuild_table_with_columns(
        conn,
        table_name="wiki_revision_monitor_article_results",
        create_sql=ARTICLE_RESULTS_CREATE_SQL,
        target_columns=[
            "run_id",
            "article_id",
            "status",
            "previous_revid",
            "current_revid",
            "top_severity",
            "snapshot_path",
            "timeline_path",
            "aoo_path",
            "report_path",
        ],
    )
    _rebuild_table_with_columns(
        conn,
        table_name="wiki_revision_monitor_candidate_pairs",
        create_sql=CANDIDATE_PAIRS_CREATE_SQL,
        target_columns=[
            "run_id",
            "article_id",
            "pair_id",
            "pair_kind",
            "older_revid",
            "newer_revid",
            "selected",
            "score",
            "pair_report_path",
            "status",
        ],
    )
    _rebuild_table_with_columns(
        conn,
        table_name="wiki_revision_monitor_contested_graphs",
        create_sql=CONTESTED_GRAPHS_CREATE_SQL,
        target_columns=[
            "run_id",
            "article_id",
            "graph_path",
            "region_count",
            "cycle_count",
            "selected_pair_count",
            "changed_event_count",
            "changed_attribution_count",
            "highest_severity",
            "hottest_region_json",
        ],
    )
    ensure_read_model_schema(conn)


def _store_pack_manifest(conn: sqlite3.Connection, *, pack_path: Path, pack: Mapping[str, Any]) -> None:
    ensure_revision_pack_schema(conn)
    pack_id = str(pack.get("pack_id") or "").strip()
    manifest_json = stable_json(pack)
    manifest_sha256 = __import__("hashlib").sha256(manifest_json.encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_packs(
          pack_id, version, scope, manifest_path, manifest_sha256, manifest_json, updated_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(pack_id) DO UPDATE SET
          version=excluded.version,
          scope=excluded.scope,
          manifest_path=excluded.manifest_path,
          manifest_sha256=excluded.manifest_sha256,
          manifest_json=excluded.manifest_json,
          updated_at=excluded.updated_at
        """,
        (
            pack_id,
            int(pack.get("version") or 0),
            str(pack.get("scope") or ""),
            str(pack_path),
            manifest_sha256,
            manifest_json,
            _utc_now_iso(),
        ),
    )
    conn.execute("DELETE FROM wiki_revision_monitor_articles WHERE pack_id = ?", (pack_id,))
    for index, article in enumerate(pack.get("articles") or []):
        if not isinstance(article, Mapping):
            continue
        conn.execute(
            """
            INSERT INTO wiki_revision_monitor_articles(
              article_id, pack_id, wiki, title, role, topics_json, review_context_json, article_order
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(article_id) DO UPDATE SET
              pack_id=excluded.pack_id,
              wiki=excluded.wiki,
              title=excluded.title,
              role=excluded.role,
              topics_json=excluded.topics_json,
              review_context_json=excluded.review_context_json,
              article_order=excluded.article_order
            """,
            (
                str(article.get("article_id") or f"article_{index+1:03d}"),
                pack_id,
                str(article.get("wiki") or "enwiki"),
                str(article.get("title") or ""),
                str(article.get("role") or "stress"),
                json.dumps(article.get("topics") or [], sort_keys=True),
                json.dumps(article.get("review_context") or {}, sort_keys=True),
                index,
            ),
        )


def _load_article_state(conn: sqlite3.Connection, article_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT article_id, last_revid, last_rev_timestamp, last_fetched_at,
               snapshot_path, timeline_path, aoo_path, report_path, status, updated_at
        FROM wiki_revision_monitor_article_state
        WHERE article_id = ?
        """,
        (article_id,),
    ).fetchone()


def _upsert_article_state(
    conn: sqlite3.Connection,
    *,
    article_id: str,
    revid: int | None,
    rev_timestamp: str | None,
    fetched_at: str | None,
    snapshot_path: Path | None,
    timeline_path: Path | None,
    aoo_path: Path | None,
    report_path: Path | None,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_article_state(
          article_id, last_revid, last_rev_timestamp, last_fetched_at,
          snapshot_path, timeline_path, aoo_path, report_path, status, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(article_id) DO UPDATE SET
          last_revid=excluded.last_revid,
          last_rev_timestamp=excluded.last_rev_timestamp,
          last_fetched_at=excluded.last_fetched_at,
          snapshot_path=excluded.snapshot_path,
          timeline_path=excluded.timeline_path,
          aoo_path=excluded.aoo_path,
          report_path=excluded.report_path,
          status=excluded.status,
          updated_at=excluded.updated_at
        """,
        (
            article_id,
            revid,
            rev_timestamp,
            fetched_at,
            str(snapshot_path) if snapshot_path else None,
            str(timeline_path) if timeline_path else None,
            str(aoo_path) if aoo_path else None,
            str(report_path) if report_path else None,
            status,
            _utc_now_iso(),
        ),
    )


def _insert_run(conn: sqlite3.Connection, *, run_id: str, pack_id: str, started_at: str, out_dir: Path) -> None:
    conn.execute(
        """
        INSERT INTO wiki_revision_monitor_runs(run_id, pack_id, started_at, completed_at, status, out_dir)
        VALUES(?,?,?,?,?,?)
        """,
        (run_id, pack_id, started_at, None, "running", str(out_dir)),
    )


def _complete_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    status: str,
    summary: Mapping[str, Any],
    completed_at: str,
) -> None:
    conn.execute(
        """
        UPDATE wiki_revision_monitor_runs
        SET completed_at = ?, status = ?
        WHERE run_id = ?
        """,
        (completed_at, status, run_id),
    )


def _insert_article_result(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    status: str,
    previous_revid: int | None,
    current_revid: int | None,
    top_severity: str,
    packet_counts: Mapping[str, Any],
    snapshot_path: Path | None,
    timeline_path: Path | None,
    aoo_path: Path | None,
    report_path: Path | None,
    result_payload: Mapping[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO wiki_revision_monitor_article_results(
          run_id, article_id, status, previous_revid, current_revid, top_severity,
          snapshot_path, timeline_path, aoo_path, report_path
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            article_id,
            status,
            previous_revid,
            current_revid,
            top_severity,
            str(snapshot_path) if snapshot_path else None,
            str(timeline_path) if timeline_path else None,
            str(aoo_path) if aoo_path else None,
            str(report_path) if report_path else None,
        ),
    )


def _insert_history_rows(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    rows: list[dict[str, Any]],
) -> None:
    for index, row in enumerate(rows):
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_history_rows(
              run_id, article_id, row_order, revid, parentid, timestamp, size, comment, row_json
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                index,
                _safe_int(row.get("revid")),
                _safe_int(row.get("parentid")),
                _norm_text(row.get("timestamp")) or None,
                _safe_int(row.get("size")),
                _norm_text(row.get("comment")) or None,
                json.dumps(row, sort_keys=True),
            ),
        )


def _insert_candidate_pair(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    pair_payload: Mapping[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO wiki_revision_monitor_candidate_pairs(
          run_id, article_id, pair_id, pair_kind, older_revid, newer_revid, selected, score,
          pair_report_path, status
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            article_id,
            str(pair_payload.get("pair_id")),
            str(pair_payload.get("pair_kind")),
            _safe_int(pair_payload.get("older_revid")),
            _safe_int(pair_payload.get("newer_revid")),
            1 if pair_payload.get("selected") else 0,
            float(pair_payload.get("candidate_score") or 0.0),
            str(pair_payload.get("pair_report_path") or "") or None,
            str(pair_payload.get("status") or "candidate"),
        ),
    )


def _insert_contested_graph(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    article_id: str,
    graph_path: Path,
    graph_payload: Mapping[str, Any],
) -> None:
    summary = graph_payload.get("summary") if isinstance(graph_payload.get("summary"), Mapping) else {}
    conn.execute(
        """
        INSERT OR REPLACE INTO wiki_revision_monitor_contested_graphs(
          run_id, article_id, graph_path, region_count, cycle_count, selected_pair_count,
          changed_event_count, changed_attribution_count, highest_severity, hottest_region_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            article_id,
            str(graph_path),
            int(summary.get("region_count") or 0),
            int(summary.get("cycle_count") or 0),
            int(summary.get("selected_pair_count") or 0),
            int(summary.get("changed_event_count") or 0),
            int(summary.get("changed_attribution_count") or 0),
            str(summary.get("highest_severity") or "none"),
            json.dumps(summary.get("hottest_region") or None, sort_keys=True),
        ),
    )
    for region in graph_payload.get("regions") or []:
        if not isinstance(region, Mapping):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_contested_regions(
              run_id, article_id, region_id, title, touch_count, total_touched_bytes, highest_severity, region_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(region.get("region_id") or ""),
                str(region.get("title") or ""),
                int(region.get("touch_count") or 0),
                int(region.get("total_touched_bytes") or 0),
                str(region.get("highest_severity") or "none"),
                json.dumps(region, sort_keys=True),
            ),
        )
    for cycle in graph_payload.get("cycles") or []:
        if not isinstance(cycle, Mapping):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_contested_cycles(
              run_id, article_id, cycle_id, region_id, touch_count, highest_severity, cycle_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(cycle.get("cycle_id") or ""),
                str(cycle.get("region_id") or ""),
                int(cycle.get("touch_count") or 0),
                str(cycle.get("highest_severity") or "none"),
                json.dumps(cycle, sort_keys=True),
            ),
        )
    for edge in graph_payload.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_contested_edges(
              run_id, article_id, edge_id, edge_kind, source_id, target_id, edge_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(edge.get("edge_id") or ""),
                str(edge.get("edge_kind") or ""),
                str(edge.get("source_id") or ""),
                str(edge.get("target_id") or ""),
                json.dumps(edge, sort_keys=True),
            ),
        )
    for event in graph_payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_contested_events(
              run_id, article_id, event_id, event_json
            ) VALUES(?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(event.get("event_id") or ""),
                json.dumps(event, sort_keys=True),
            ),
        )
    for epistemic in graph_payload.get("epistemic_surfaces") or []:
        if not isinstance(epistemic, Mapping):
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_revision_monitor_contested_epistemic(
              run_id, article_id, epistemic_id, epistemic_json
            ) VALUES(?,?,?,?)
            """,
            (
                run_id,
                article_id,
                str(epistemic.get("epistemic_id") or ""),
                json.dumps(epistemic, sort_keys=True),
            ),
        )


def _subprocess_json(args: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def _looks_like_person_title(title: str) -> bool:
    parts = [part for part in _norm_text(title).split(" ") if part]
    if len(parts) < 2 or len(parts) > 4:
        return False
    if any(part.lower() in {"language", "languages", "park", "system", "space", "alphabet", "conflict"} for part in parts):
        return False
    return all(part[:1].isupper() for part in parts)


def _default_fetch_current_snapshot(
    *,
    article: Mapping[str, Any],
    out_dir: Path,
    python_cmd: str,
    repo_root: Path,
) -> dict[str, Any]:
    payload = _subprocess_json(
        [
            python_cmd,
            str(repo_root / "SensibLaw" / "scripts" / "wiki_pull_api.py"),
            "--wiki",
            str(article.get("wiki") or "enwiki"),
            "--title",
            str(article.get("title") or ""),
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
    )
    snapshots = payload.get("snapshots") or []
    if not snapshots:
        raise RuntimeError(f"wiki pull returned no snapshots for {article.get('title')}")
    snapshot_path = Path(str(snapshots[0]))
    snapshot_payload = read_json_file(snapshot_path)
    if snapshot_payload is None:
        raise RuntimeError(f"snapshot file unreadable: {snapshot_path}")
    return {"snapshot_path": snapshot_path, "snapshot_payload": snapshot_payload}


def _default_fetch_revision_snapshot(
    *,
    article: Mapping[str, Any],
    revid: int,
    out_dir: Path,
    python_cmd: str,
    repo_root: Path,
) -> dict[str, Any]:
    payload = _subprocess_json(
        [
            python_cmd,
            str(repo_root / "SensibLaw" / "scripts" / "wiki_pull_api.py"),
            "--wiki",
            str(article.get("wiki") or "enwiki"),
            "--title",
            str(article.get("title") or ""),
            "--revid",
            str(revid),
            "--out-dir",
            str(out_dir),
        ],
        cwd=repo_root,
    )
    snapshots = payload.get("snapshots") or []
    if not snapshots:
        raise RuntimeError(f"wiki pull returned no snapshot for revision {revid}")
    snapshot_path = Path(str(snapshots[0]))
    snapshot_payload = read_json_file(snapshot_path)
    if snapshot_payload is None:
        raise RuntimeError(f"snapshot file unreadable: {snapshot_path}")
    return {"snapshot_path": snapshot_path, "snapshot_payload": snapshot_payload}


def _default_fetch_revision_history(
    *,
    article: Mapping[str, Any],
    out_dir: Path,
    python_cmd: str,
    repo_root: Path,
    max_revisions: int,
    window_days: int,
) -> dict[str, Any]:
    args = [
        python_cmd,
        str(repo_root / "SensibLaw" / "scripts" / "wiki_pull_api.py"),
        "--wiki",
        str(article.get("wiki") or "enwiki"),
        "--title",
        str(article.get("title") or ""),
        "--out-dir",
        str(out_dir),
        "--history-max-revisions",
        str(max_revisions),
    ]
    if window_days > 0:
        args.extend(["--history-window-days", str(window_days)])
    payload = _subprocess_json(args, cwd=repo_root)
    histories = payload.get("histories") or []
    if not histories:
        return {"history_path": None, "history_payload": {"rows": [], "warnings": ["no_history_manifest"]}}
    history_path = Path(str(histories[0]))
    history_payload = read_json_file(history_path)
    if history_payload is None:
        raise RuntimeError(f"history manifest unreadable: {history_path}")
    return {"history_path": history_path, "history_payload": history_payload}


def _default_build_timeline(
    *,
    snapshot_path: Path,
    out_path: Path,
    python_cmd: str,
    repo_root: Path,
) -> dict[str, Any]:
    _subprocess_json(
        [
            python_cmd,
            str(repo_root / "SensibLaw" / "scripts" / "wiki_timeline_extract.py"),
            "--snapshot",
            str(snapshot_path),
            "--out",
            str(out_path),
        ],
        cwd=repo_root,
    )
    payload = read_json_file(out_path)
    if payload is None:
        raise RuntimeError(f"timeline file unreadable: {out_path}")
    return {"timeline_path": out_path, "timeline_payload": payload}


def _default_build_aoo(
    *,
    article: Mapping[str, Any],
    timeline_path: Path,
    out_path: Path,
    python_cmd: str,
    repo_root: Path,
) -> dict[str, Any]:
    args = [
        python_cmd,
        str(repo_root / "SensibLaw" / "scripts" / "wiki_timeline_aoo_extract.py"),
        "--timeline",
        str(timeline_path),
        "--out",
        str(out_path),
        "--no-db",
    ]
    title = str(article.get("title") or "")
    if _looks_like_person_title(title):
        args.extend(["--root-actor", title, "--root-surname", title.split()[-1]])
    _subprocess_json(args, cwd=repo_root)
    payload = read_json_file(out_path)
    if payload is None:
        raise RuntimeError(f"aoo file unreadable: {out_path}")
    return {"aoo_path": out_path, "aoo_payload": payload}


def _default_auto_review_context(
    *,
    packet: Mapping[str, Any],
    article: Mapping[str, Any],
    bridge_db_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.ontology.entity_bridge import lookup_bridge_alias  # noqa: PLC0415

    db_path = bridge_db_path or Path(".cache_local/itir.sqlite")
    surfaces = {_norm_text(article.get("title"))}
    for surface in packet.get("related_entities") or []:
        norm = _norm_text(surface)
        if norm:
            surfaces.add(norm)
    hits: dict[tuple[str, str], dict[str, Any]] = {}
    for surface in sorted(surfaces):
        for link in lookup_bridge_alias(surface, db_path=db_path):
            key = (link.canonical_ref, link.curie)
            if key not in hits:
                hits[key] = {
                    "canonical_ref": link.canonical_ref,
                    "canonical_kind": link.canonical_kind,
                    "provider": link.provider,
                    "external_id": link.external_id,
                    "curie": link.curie,
                    "matched_alias": link.matched_alias,
                    "source_surface": surface,
                    "slice_name": link.slice_name,
                }
    return {"auto_bridge_matches": sorted(hits.values(), key=lambda row: (row["canonical_kind"], row["canonical_ref"], row["curie"]))}


def _merge_packet_review_context(
    *,
    report: dict[str, Any],
    article: Mapping[str, Any],
    auto_review_context_fn: Callable[..., Mapping[str, Any]] | None = None,
    bridge_db_path: Path | None = None,
    section_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    curated_context = article.get("review_context") if isinstance(article.get("review_context"), Mapping) else {}
    packets = report.get("issue_packets")
    if not isinstance(packets, list):
        return report
    for packet in packets:
        if not isinstance(packet, dict):
            continue
        review_context: dict[str, Any] = {}
        if curated_context:
            review_context["curated"] = curated_context
        if auto_review_context_fn is not None:
            try:
                auto_ctx = auto_review_context_fn(packet=packet, article=article, bridge_db_path=bridge_db_path)
            except Exception as exc:
                auto_ctx = {"auto_context_error": f"{type(exc).__name__}: {exc}"}
            if auto_ctx:
                review_context.update(auto_ctx)
        if review_context:
            packet["review_context"] = review_context
        if section_context:
            packet["section_context"] = section_context
    return report


def _history_config(pack: Mapping[str, Any], article: Mapping[str, Any]) -> dict[str, int]:
    defaults = pack.get("history_defaults") if isinstance(pack.get("history_defaults"), Mapping) else {}
    article_history = article.get("history") if isinstance(article.get("history"), Mapping) else {}

    def pick(name: str, fallback: int) -> int:
        val = article_history.get(name, defaults.get(name, fallback))
        return max(0, int(val or 0))

    return {
        "max_revisions": pick("max_revisions", 20),
        "window_days": pick("window_days", 14),
        "max_candidate_pairs": max(1, pick("max_candidate_pairs", 3)),
        "section_focus_limit": max(1, pick("section_focus_limit", 5)),
    }


def _graph_enabled(pack: Mapping[str, Any], article: Mapping[str, Any]) -> bool:
    if isinstance(article.get("graph_enabled"), bool):
        return bool(article.get("graph_enabled"))
    if isinstance(pack.get("graph_enabled"), bool):
        return bool(pack.get("graph_enabled"))
    return False


def _normalize_history_rows(history_payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(history_payload, Mapping):
        return []
    rows = history_payload.get("rows")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        out.append(
            {
                "revid": _safe_int(row.get("revid")),
                "parentid": _safe_int(row.get("parentid")),
                "timestamp": _norm_text(row.get("timestamp")) or None,
                "size": _safe_int(row.get("size")),
                "comment": _norm_text(row.get("comment")) or None,
                "user": _norm_text(row.get("user")) or None,
                "anon": bool(row.get("anon")),
            }
        )
    out.sort(key=_history_row_sort_key, reverse=True)
    return out


def _ensure_history_contains_current(rows: list[dict[str, Any]], current_snapshot_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    current_revid = _safe_int(current_snapshot_payload.get("revid"))
    if current_revid is None:
        return rows
    if any(_safe_int(row.get("revid")) == current_revid for row in rows):
        return rows
    rows = list(rows)
    rows.insert(
        0,
        {
            "revid": current_revid,
            "parentid": None,
            "timestamp": _norm_text(current_snapshot_payload.get("rev_timestamp")) or None,
            "size": len(str(current_snapshot_payload.get("wikitext") or "")),
            "comment": None,
            "user": None,
            "anon": False,
        },
    )
    rows.sort(key=_history_row_sort_key, reverse=True)
    return rows


def _add_candidate_pair(
    candidates: dict[tuple[int, int], dict[str, Any]],
    *,
    kind: str,
    older: Mapping[str, Any] | None,
    newer: Mapping[str, Any] | None,
    previous_revid: int | None = None,
) -> None:
    older_revid = _safe_int(older.get("revid")) if isinstance(older, Mapping) else previous_revid
    newer_revid = _safe_int(newer.get("revid")) if isinstance(newer, Mapping) else None
    if older_revid is None or newer_revid is None or older_revid == newer_revid:
        return
    if older_revid > newer_revid:
        older_revid, newer_revid = newer_revid, older_revid
        older, newer = newer, older
    key = (older_revid, newer_revid)
    payload = candidates.setdefault(
        key,
        {
            "pair_id": f"pair:{kind}:{older_revid}:{newer_revid}",
            "pair_kind": kind,
            "pair_kinds": [],
            "older_revid": older_revid,
            "newer_revid": newer_revid,
            "older_row": dict(older or {}),
            "newer_row": dict(newer or {}),
        },
    )
    if kind not in payload["pair_kinds"]:
        payload["pair_kinds"].append(kind)
    if payload["pair_kind"] != "last_seen_current" and kind == "last_seen_current":
        payload["pair_kind"] = kind


def _candidate_pairs(rows: list[dict[str, Any]], previous_state: sqlite3.Row | None, current_revid: int | None) -> list[dict[str, Any]]:
    candidates: dict[tuple[int, int], dict[str, Any]] = {}
    previous_revid = int(previous_state["last_revid"]) if previous_state and previous_state["last_revid"] is not None else None
    current_row = next((row for row in rows if _safe_int(row.get("revid")) == current_revid), rows[0] if rows else None)

    if previous_revid is not None and current_revid is not None and previous_revid != current_revid:
        _add_candidate_pair(candidates, kind="last_seen_current", older={"revid": previous_revid}, newer=current_row, previous_revid=previous_revid)

    if len(rows) >= 2:
        _add_candidate_pair(candidates, kind="previous_current", older=rows[1], newer=rows[0])
        largest = max(
            zip(rows[1:], rows[:-1]),
            key=lambda pair: abs((_safe_int(pair[0].get("size")) or 0) - (_safe_int(pair[1].get("size")) or 0)),
        )
        _add_candidate_pair(candidates, kind="largest_delta_in_window", older=largest[0], newer=largest[1])

        reverted_pairs = [
            (older, newer)
            for older, newer in zip(rows[1:], rows[:-1])
            if _REVERT_RE.search(str(newer.get("comment") or "")) or _REVERT_RE.search(str(older.get("comment") or ""))
        ]
        if reverted_pairs:
            reverted = reverted_pairs[0]
            _add_candidate_pair(candidates, kind="most_reverted_like_in_window", older=reverted[0], newer=reverted[1])

    return list(candidates.values())


def _split_sections(wikitext: str) -> dict[str, str]:
    text = str(wikitext or "")
    if not text.strip():
        return {}
    sections: dict[str, str] = {}
    current = "(lead)"
    last = 0
    for match in _SECTION_RE.finditer(text):
        sections[current] = sections.get(current, "") + text[last : match.start()]
        current = _norm_text(match.group(2)) or current
        last = match.end()
    sections[current] = sections.get(current, "") + text[last:]
    return {key: value for key, value in sections.items() if value is not None}


def _section_delta_summary(
    older_snapshot_payload: Mapping[str, Any],
    newer_snapshot_payload: Mapping[str, Any],
    *,
    limit: int,
) -> dict[str, Any]:
    older_sections = _split_sections(str(older_snapshot_payload.get("wikitext") or ""))
    newer_sections = _split_sections(str(newer_snapshot_payload.get("wikitext") or ""))
    if not older_sections and not newer_sections:
        return {
            "available": False,
            "unknown_section_alignment": True,
            "changed_section_count": 0,
            "section_touch_size": 0,
            "top_changed_sections": [],
        }
    changed: list[dict[str, Any]] = []
    for title in sorted(set(older_sections) | set(newer_sections)):
        older_text = older_sections.get(title, "")
        newer_text = newer_sections.get(title, "")
        if older_text == newer_text:
            continue
        older_len = len(older_text)
        newer_len = len(newer_text)
        touched = abs(newer_len - older_len) + max(older_len, newer_len)
        changed.append(
            {
                "section": title,
                "older_length": older_len,
                "newer_length": newer_len,
                "touched_bytes": touched,
            }
        )
    changed.sort(key=lambda row: (-int(row["touched_bytes"]), row["section"]))
    return {
        "available": True,
        "unknown_section_alignment": False,
        "changed_section_count": len(changed),
        "section_touch_size": sum(int(row["touched_bytes"]) for row in changed),
        "top_changed_sections": changed[: max(1, int(limit))],
    }


def _burst_signal(older_row: Mapping[str, Any], newer_row: Mapping[str, Any]) -> float:
    older_ts = _parse_iso_datetime(older_row.get("timestamp"))
    newer_ts = _parse_iso_datetime(newer_row.get("timestamp"))
    if older_ts is None or newer_ts is None:
        return 0.0
    delta_s = abs((newer_ts - older_ts).total_seconds())
    if delta_s <= 3600:
        return 1.0
    if delta_s <= 6 * 3600:
        return 0.6
    if delta_s <= 24 * 3600:
        return 0.25
    return 0.0


def _score_candidate_pair(
    pair: dict[str, Any],
    *,
    older_snapshot_payload: Mapping[str, Any],
    newer_snapshot_payload: Mapping[str, Any],
    section_focus_limit: int,
) -> dict[str, Any]:
    older_row = pair.get("older_row") or {}
    newer_row = pair.get("newer_row") or {}
    older_size = _safe_int(older_row.get("size")) or len(str(older_snapshot_payload.get("wikitext") or ""))
    newer_size = _safe_int(newer_row.get("size")) or len(str(newer_snapshot_payload.get("wikitext") or ""))
    byte_delta = abs(newer_size - older_size)
    revert_signal = 1.0 if (_REVERT_RE.search(str(newer_row.get("comment") or "")) or _REVERT_RE.search(str(older_row.get("comment") or ""))) else 0.0
    burst_signal = _burst_signal(older_row, newer_row)
    section_delta = _section_delta_summary(older_snapshot_payload, newer_snapshot_payload, limit=section_focus_limit)
    section_touch_size = int(section_delta.get("section_touch_size") or 0)
    total_score = float(byte_delta) + (500.0 * revert_signal) + (250.0 * burst_signal) + (0.1 * section_touch_size)
    return {
        "candidate_score": round(total_score, 3),
        "score_breakdown": {
            "byte_delta": byte_delta,
            "revert_signal": revert_signal,
            "edit_burst_signal": burst_signal,
            "section_touch_size": section_touch_size,
        },
        "section_delta_summary": section_delta,
    }


def _pair_graph_extract(pair_report_path: str | None) -> dict[str, Any]:
    payload = read_json_file(Path(str(pair_report_path))) if pair_report_path else None
    if not isinstance(payload, Mapping):
        return {
            "changed_event_ids": [],
            "changed_attribution_event_ids": [],
            "added_claim_bearing_event_ids": [],
            "removed_claim_bearing_event_ids": [],
            "material_graph_change": False,
        }
    comparison = payload.get("comparison_report") if isinstance(payload.get("comparison_report"), Mapping) else {}
    extraction = comparison.get("extraction_delta_summary") if isinstance(comparison.get("extraction_delta_summary"), Mapping) else {}
    epistemic = comparison.get("epistemic_delta_summary") if isinstance(comparison.get("epistemic_delta_summary"), Mapping) else {}
    graph = comparison.get("graph_impact_summary") if isinstance(comparison.get("graph_impact_summary"), Mapping) else {}
    changed_events = set()
    for key in ("changed_event_ids", "added_event_ids", "removed_event_ids"):
        for item in extraction.get(key) or []:
            changed_events.add(str(item))
    return {
        "changed_event_ids": sorted(changed_events),
        "changed_attribution_event_ids": sorted(str(item) for item in (epistemic.get("changed_attribution_event_ids") or [])),
        "added_claim_bearing_event_ids": sorted(str(item) for item in (epistemic.get("added_claim_bearing_event_ids") or [])),
        "removed_claim_bearing_event_ids": sorted(str(item) for item in (epistemic.get("removed_claim_bearing_event_ids") or [])),
        "material_graph_change": bool(graph.get("material_change")),
    }


def _selected_issue_packet_rows(selected_pairs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in selected_pairs:
        pair_id = str(pair.get("pair_id") or "")
        report_path = pair.get("pair_report_path")
        payload = read_json_file(Path(str(report_path))) if report_path else None
        if not isinstance(payload, Mapping):
            continue
        comparison = payload.get("comparison_report") if isinstance(payload.get("comparison_report"), Mapping) else {}
        issue_packets = comparison.get("issue_packets") if isinstance(comparison.get("issue_packets"), list) else []
        for index, packet in enumerate(issue_packets):
            if not isinstance(packet, Mapping):
                continue
            row = dict(packet)
            row["pair_id"] = pair_id
            row["packet_order"] = index
            rows.append(row)
    return rows


def _selected_pair_rows(selected_pairs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in selected_pairs:
        if not isinstance(pair, Mapping):
            continue
        rows.append(
            {
                "pair_id": str(pair.get("pair_id") or ""),
                "pair_kind": str(pair.get("pair_kind") or ""),
                "pair_kinds": list(pair.get("pair_kinds") or []),
                "older_revid": pair.get("older_revid"),
                "newer_revid": pair.get("newer_revid"),
                "candidate_score": pair.get("candidate_score"),
                "top_severity": pair.get("top_severity", "none"),
                "pair_report_path": pair.get("pair_report_path"),
                "top_changed_sections": list(((pair.get("section_delta_summary") or {}).get("top_changed_sections")) or []),
            }
        )
    return rows


def _build_contested_region_graph(
    *,
    article: Mapping[str, Any],
    run_id: str,
    selected_pairs: list[dict[str, Any]],
    out_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    article_id = str(article.get("article_id") or "")
    title = str(article.get("title") or "")
    graph_path = graph_artifact_path(out_dir=out_dir, article_id=article_id, run_id=run_id)
    regions: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []
    pair_nodes: list[dict[str, Any]] = []
    event_nodes: dict[str, dict[str, Any]] = {}
    epistemic_nodes: dict[str, dict[str, Any]] = {}
    pair_regions: dict[str, list[str]] = {}

    for pair in selected_pairs:
        pair_id = str(pair.get("pair_id") or "")
        pair_kind = str(pair.get("pair_kind") or "")
        pair_nodes.append(
            {
                "pair_id": pair_id,
                "pair_kind": pair_kind,
                "pair_kinds": list(pair.get("pair_kinds") or []),
                "older_revid": pair.get("older_revid"),
                "newer_revid": pair.get("newer_revid"),
                "candidate_score": pair.get("candidate_score"),
                "top_severity": pair.get("top_severity", "none"),
                "pair_report_path": pair.get("pair_report_path"),
            }
        )
        graph_extract = _pair_graph_extract(pair.get("pair_report_path"))
        pair["graph_extract"] = graph_extract
        region_ids: list[str] = []
        for section in ((pair.get("section_delta_summary") or {}).get("top_changed_sections") or []):
            if not isinstance(section, Mapping):
                continue
            section_title = str(section.get("section") or "").strip() or "(unknown)"
            region_id = f"region:{slug_artifact_name(section_title)}"
            region_ids.append(region_id)
            region = regions.setdefault(
                region_id,
                {
                    "region_id": region_id,
                    "title": section_title,
                    "touch_count": 0,
                    "total_touched_bytes": 0,
                    "pair_ids": [],
                    "pair_kinds": [],
                    "changed_event_ids": [],
                    "changed_attribution_event_ids": [],
                    "highest_severity": "none",
                    "graph_heat": 0.0,
                },
            )
            region["touch_count"] = int(region.get("touch_count") or 0) + 1
            region["total_touched_bytes"] = int(region.get("total_touched_bytes") or 0) + int(section.get("touched_bytes") or 0)
            if pair_id not in region["pair_ids"]:
                region["pair_ids"].append(pair_id)
            if pair_kind and pair_kind not in region["pair_kinds"]:
                region["pair_kinds"].append(pair_kind)
            region["changed_event_ids"] = sorted(set(region.get("changed_event_ids") or []).union(graph_extract["changed_event_ids"]))
            region["changed_attribution_event_ids"] = sorted(
                set(region.get("changed_attribution_event_ids") or []).union(graph_extract["changed_attribution_event_ids"])
            )
            if severity_rank(pair.get("top_severity")) > severity_rank(region.get("highest_severity")):
                region["highest_severity"] = str(pair.get("top_severity") or "none")
            edges.append(
                {
                    "edge_id": f"edge:touches_region:{pair_id}:{region_id}",
                    "edge_kind": "touches_region",
                    "source_id": pair_id,
                    "target_id": region_id,
                    "weight": int(section.get("touched_bytes") or 0),
                }
            )
            if severity_rank(pair.get("top_severity")) > 0:
                edges.append(
                    {
                        "edge_id": f"edge:escalates_region:{pair_id}:{region_id}",
                        "edge_kind": "escalates_region",
                        "source_id": pair_id,
                        "target_id": region_id,
                        "severity": str(pair.get("top_severity") or "none"),
                    }
                )
            for event_id in graph_extract["changed_event_ids"]:
                event_nodes.setdefault(event_id, {"event_id": event_id})
                edges.append(
                    {
                        "edge_id": f"edge:changes_event:{pair_id}:{event_id}",
                        "edge_kind": "changes_event",
                        "source_id": pair_id,
                        "target_id": event_id,
                    }
                )
                edges.append(
                    {
                        "edge_id": f"edge:co_occurs_in_region:{event_id}:{region_id}",
                        "edge_kind": "co_occurs_in_region",
                        "source_id": event_id,
                        "target_id": region_id,
                    }
                )
            for event_id in graph_extract["changed_attribution_event_ids"]:
                epi_id = f"epi:{event_id}"
                epistemic_nodes.setdefault(epi_id, {"epistemic_id": epi_id, "event_id": event_id})
                edges.append(
                    {
                        "edge_id": f"edge:changes_attribution:{pair_id}:{epi_id}",
                        "edge_kind": "changes_attribution",
                        "source_id": pair_id,
                        "target_id": epi_id,
                    }
                )
        pair_regions[pair_id] = region_ids

    pair_nodes.sort(key=lambda item: (int(item.get("newer_revid") or 0), int(item.get("older_revid") or 0), str(item.get("pair_id") or "")))
    for index in range(1, len(pair_nodes)):
        older = pair_nodes[index - 1]
        newer = pair_nodes[index]
        edges.append(
            {
                "edge_id": f"edge:revises_after:{older['pair_id']}:{newer['pair_id']}",
                "edge_kind": "revises_after",
                "source_id": older["pair_id"],
                "target_id": newer["pair_id"],
            }
        )

    for region in regions.values():
        region["graph_heat"] = round(
            float(region["total_touched_bytes"]) + (250.0 * severity_rank(region["highest_severity"])) + (125.0 * len(region["changed_attribution_event_ids"])),
            3,
        )
        if int(region["touch_count"] or 0) >= 3 or (int(region["touch_count"] or 0) >= 2 and len(region["pair_kinds"]) >= 2):
            cycle_id = f"cycle:{region['region_id']}"
            reason = "multi_pair_kind_return" if len(region["pair_kinds"]) >= 2 else "repeat_region_touch"
            cycles.append(
                {
                    "cycle_id": cycle_id,
                    "region_id": region["region_id"],
                    "region_title": region["title"],
                    "pair_ids": list(region["pair_ids"]),
                    "pair_kinds": list(region["pair_kinds"]),
                    "touch_count": region["touch_count"],
                    "total_touched_bytes": region["total_touched_bytes"],
                    "highest_severity": region["highest_severity"],
                    "reason": reason,
                }
            )
            for pair_id in region["pair_ids"]:
                edges.append(
                    {
                        "edge_id": f"edge:returns_to_region:{pair_id}:{region['region_id']}",
                        "edge_kind": "returns_to_region",
                        "source_id": pair_id,
                        "target_id": region["region_id"],
                        "reason": reason,
                    }
                )

    ranked_regions = sorted(
        regions.values(),
        key=lambda item: (-float(item.get("graph_heat") or 0.0), -int(item.get("touch_count") or 0), str(item.get("title") or "")),
    )
    hottest_region = ranked_regions[0] if ranked_regions else None
    highest_severity = "none"
    for candidate in ("high", "medium", "low"):
        if any(region.get("highest_severity") == candidate for region in ranked_regions) or any(cycle.get("highest_severity") == candidate for cycle in cycles):
            highest_severity = candidate
            break
    graph_heat = round(sum(float(region.get("graph_heat") or 0.0) for region in ranked_regions), 3)
    summary = {
        "region_count": len(ranked_regions),
        "selected_pair_count": len(pair_nodes),
        "changed_event_count": len(event_nodes),
        "changed_attribution_count": len(epistemic_nodes),
        "cycle_count": len(cycles),
        "highest_severity": highest_severity,
        "partial": False,
        "graph_heat": graph_heat,
        "hottest_region": hottest_region,
        "top_regions": ranked_regions[:5],
        "top_cycles": sorted(cycles, key=lambda item: (-severity_rank(item.get("highest_severity")), -int(item.get("touch_count") or 0), str(item.get("region_title") or "")))[:5],
    }
    payload = {
        "schema_version": CONTESTED_GRAPH_SCHEMA_VERSION,
        "article": {
            "article_id": article_id,
            "title": title,
            "wiki": str(article.get("wiki") or "enwiki"),
        },
        "run": {"run_id": run_id},
        "regions": ranked_regions,
        "selected_pairs": pair_nodes,
        "events": sorted(event_nodes.values(), key=lambda item: str(item.get("event_id") or "")),
        "epistemic_surfaces": sorted(epistemic_nodes.values(), key=lambda item: str(item.get("epistemic_id") or "")),
        "edges": edges,
        "cycles": cycles,
        "summary": summary,
    }
    write_json_file(graph_path, payload)
    latest_path = out_dir / "contested_graphs" / f"{slug_artifact_name(article_id)}__latest.json"
    write_json_file(latest_path, payload)
    return graph_path, payload


def _build_pair_report(
    *,
    article: Mapping[str, Any],
    pair: dict[str, Any],
    out_dir: Path,
    python_cmd: str,
    repo_root: Path,
    fetch_revision_snapshot_fn: Callable[..., Mapping[str, Any]],
    build_timeline_fn: Callable[..., Mapping[str, Any]],
    build_aoo_fn: Callable[..., Mapping[str, Any]],
    auto_review_context_fn: Callable[..., Mapping[str, Any]] | None,
    bridge_db_path: Path | None,
    section_focus_limit: int,
) -> dict[str, Any]:
    older_revid = int(pair["older_revid"])
    newer_revid = int(pair["newer_revid"])
    pair_paths = pair_artifact_paths(
        out_dir=out_dir,
        article_id=str(article.get("article_id") or ""),
        pair_kind=str(pair["pair_kind"]),
        older_revid=older_revid,
        newer_revid=newer_revid,
    )

    older_snapshot = fetch_revision_snapshot_fn(article=article, revid=older_revid, out_dir=out_dir / "pair_snapshots", python_cmd=python_cmd, repo_root=repo_root)
    newer_snapshot = fetch_revision_snapshot_fn(article=article, revid=newer_revid, out_dir=out_dir / "pair_snapshots", python_cmd=python_cmd, repo_root=repo_root)
    older_snapshot_payload = dict(older_snapshot["snapshot_payload"])
    newer_snapshot_payload = dict(newer_snapshot["snapshot_payload"])
    older_contract_error = _snapshot_contract_error(article, older_snapshot_payload)
    newer_contract_error = _snapshot_contract_error(article, newer_snapshot_payload)
    if older_contract_error:
        raise RuntimeError(older_contract_error)
    if newer_contract_error:
        raise RuntimeError(newer_contract_error)
    write_json_file(pair_paths["older_snapshot"], older_snapshot_payload)
    write_json_file(pair_paths["newer_snapshot"], newer_snapshot_payload)

    scoring = _score_candidate_pair(pair, older_snapshot_payload=older_snapshot_payload, newer_snapshot_payload=newer_snapshot_payload, section_focus_limit=section_focus_limit)
    pair.update(scoring)

    older_timeline = build_timeline_fn(snapshot_path=pair_paths["older_snapshot"], out_path=pair_paths["older_timeline"], python_cmd=python_cmd, repo_root=repo_root)
    newer_timeline = build_timeline_fn(snapshot_path=pair_paths["newer_snapshot"], out_path=pair_paths["newer_timeline"], python_cmd=python_cmd, repo_root=repo_root)
    older_aoo = build_aoo_fn(article=article, timeline_path=Path(str(older_timeline["timeline_path"])), out_path=pair_paths["older_aoo"], python_cmd=python_cmd, repo_root=repo_root)
    newer_aoo = build_aoo_fn(article=article, timeline_path=Path(str(newer_timeline["timeline_path"])), out_path=pair_paths["newer_aoo"], python_cmd=python_cmd, repo_root=repo_root)
    older_aoo_payload = read_json_file(Path(str(older_aoo["aoo_path"])))
    newer_aoo_payload = read_json_file(Path(str(newer_aoo["aoo_path"])))

    inner = build_revision_comparison_report(
        previous_snapshot=older_snapshot_payload,
        current_snapshot=newer_snapshot_payload,
        previous_payload=older_aoo_payload,
        current_payload=newer_aoo_payload,
    )
    section_context = list((pair.get("section_delta_summary") or {}).get("top_changed_sections") or [])
    inner = _merge_packet_review_context(
        report=inner,
        article=article,
        auto_review_context_fn=auto_review_context_fn,
        bridge_db_path=bridge_db_path,
        section_context=section_context,
    )
    wrapper = {
        "schema_version": PAIR_REPORT_SCHEMA_VERSION,
        "highest_severity": str(((inner.get("triage_dashboard") or {}).get("highest_severity")) or "none"),
        "packet_counts": dict(((inner.get("triage_dashboard") or {}).get("packet_counts")) or {}),
        "pair": {
            "pair_id": pair["pair_id"],
            "pair_kind": pair["pair_kind"],
            "pair_kinds": list(pair.get("pair_kinds") or []),
            "older_revision": {
                "revid": older_revid,
                "rev_timestamp": older_snapshot_payload.get("rev_timestamp"),
                "snapshot_path": str(pair_paths["older_snapshot"]),
            },
            "newer_revision": {
                "revid": newer_revid,
                "rev_timestamp": newer_snapshot_payload.get("rev_timestamp"),
                "snapshot_path": str(pair_paths["newer_snapshot"]),
            },
            "candidate_score": pair["candidate_score"],
            "score_breakdown": pair["score_breakdown"],
        },
        "section_delta_summary": pair["section_delta_summary"],
        "comparison_report": inner,
    }
    write_json_file(pair_paths["pair_report"], wrapper)
    pair.update(
        {
            "selected": True,
            "status": "reported",
            "pair_report_path": str(pair_paths["pair_report"]),
            "top_severity": str(((inner.get("triage_dashboard") or {}).get("highest_severity")) or "none"),
            "packet_counts": dict(((inner.get("triage_dashboard") or {}).get("packet_counts")) or {}),
        }
    )
    return pair


def run(
    *,
    pack_path: Path,
    out_dir: Path,
    state_db_path: Path,
    bridge_db_path: Path | None = None,
    python_cmd: str | None = None,
    fetch_current_snapshot_fn: Callable[..., Mapping[str, Any]] | None = None,
    fetch_revision_history_fn: Callable[..., Mapping[str, Any]] | None = None,
    fetch_revision_snapshot_fn: Callable[..., Mapping[str, Any]] | None = None,
    build_timeline_fn: Callable[..., Mapping[str, Any]] | None = None,
    build_aoo_fn: Callable[..., Mapping[str, Any]] | None = None,
    auto_review_context_fn: Callable[..., Mapping[str, Any]] | None = None,
    progress_callback: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_id = str(pack.get("pack_id") or "wiki_revision_monitor")
    run_started = _utc_now_iso()
    run_id = f"run:{pack_id}:{run_started}:{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    state_db_path.parent.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[3]
    py = python_cmd or sys.executable

    fetch_current_snapshot_fn = fetch_current_snapshot_fn or _default_fetch_current_snapshot
    fetch_revision_history_fn = fetch_revision_history_fn or _default_fetch_revision_history
    fetch_revision_snapshot_fn = fetch_revision_snapshot_fn or _default_fetch_revision_snapshot
    build_timeline_fn = build_timeline_fn or _default_build_timeline
    build_aoo_fn = build_aoo_fn or _default_build_aoo
    auto_review_context_fn = auto_review_context_fn or _default_auto_review_context

    article_results: list[dict[str, Any]] = []
    summary_counts: dict[str, int] = {"baseline_initialized": 0, "unchanged": 0, "changed": 0, "error": 0, "no_candidate_delta": 0}
    candidate_pair_counts = {"considered": 0, "selected": 0, "reported": 0}
    contested_graph_counts = {"articles_with_graphs": 0, "graphs_built": 0, "cycles_detected": 0, "regions_detected": 0}

    with sqlite3.connect(str(state_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_revision_pack_schema(conn)
        _store_pack_manifest(conn, pack_path=pack_path, pack=pack)
        _insert_run(conn, run_id=run_id, pack_id=pack_id, started_at=run_started, out_dir=out_dir)

        articles = [article for article in pack.get("articles") or [] if isinstance(article, Mapping)]
        total_articles = len(articles)
        _emit_progress(
            progress_callback,
            "revision_pack_articles_started",
            {
                "section": "wiki_revision_articles",
                "completed": 0,
                "total": max(total_articles, 1),
                "message": f"Processing {total_articles} articles.",
            },
        )

        for article_index, article in enumerate(articles, start=1):
            if not isinstance(article, Mapping):
                continue
            article_id = str(article.get("article_id") or "")
            history_cfg = _history_config(pack, article)
            previous_state = _load_article_state(conn, article_id)
            previous_revid = int(previous_state["last_revid"]) if previous_state and previous_state["last_revid"] is not None else None
            current_snapshot_path: Path | None = None
            current_timeline_path: Path | None = None
            current_aoo_path: Path | None = None
            current_report_path: Path | None = None
            contested_graph_path: Path | None = None
            contested_graph_summary: dict[str, Any] | None = None

            try:
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_started",
                    {
                        "section": "wiki_revision_articles",
                        "completed": article_index - 1,
                        "total": max(total_articles, 1),
                        "article_id": article_id,
                        "message": f"Fetching current snapshot for {article.get('title')}.",
                    },
                )
                fetched = fetch_current_snapshot_fn(article=article, out_dir=out_dir / "snapshots", python_cmd=py, repo_root=repo_root)
                current_snapshot_path = Path(str(fetched["snapshot_path"]))
                current_snapshot_payload = dict(fetched["snapshot_payload"])
                contract_error = _snapshot_contract_error(article, current_snapshot_payload)
                if contract_error:
                    raise RuntimeError(contract_error)
                current_revid = _safe_int(current_snapshot_payload.get("revid"))
                current_paths = revision_artifact_paths(out_dir=out_dir, article_id=article_id, revid=current_revid)
                if current_snapshot_path != current_paths["snapshot"]:
                    write_json_file(current_paths["snapshot"], current_snapshot_payload)
                    current_snapshot_path = current_paths["snapshot"]

                history = fetch_revision_history_fn(
                    article=article,
                    out_dir=out_dir / "history",
                    python_cmd=py,
                    repo_root=repo_root,
                    max_revisions=history_cfg["max_revisions"],
                    window_days=history_cfg["window_days"],
                )
                history_rows = _ensure_history_contains_current(_normalize_history_rows(history.get("history_payload")), current_snapshot_payload)
                _insert_history_rows(conn, run_id=run_id, article_id=article_id, rows=history_rows)
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_history",
                    {
                        "section": "wiki_revision_articles",
                        "completed": article_index - 1,
                        "total": max(total_articles, 1),
                        "article_id": article_id,
                        "message": f"Loaded {len(history_rows)} history rows.",
                        "history_row_count": len(history_rows),
                    },
                )

                selected_pairs: list[dict[str, Any]] = []
                candidates = _candidate_pairs(history_rows, previous_state, current_revid)
                scored_candidates: list[dict[str, Any]] = []
                total_candidates = len(candidates)
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_candidates_started",
                    {
                        "section": "wiki_revision_candidates",
                        "completed": 0,
                        "total": max(total_candidates, 1),
                        "article_id": article_id,
                        "message": f"Scoring {total_candidates} candidate pairs.",
                    },
                )
                for candidate_index, candidate in enumerate(candidates, start=1):
                    older_revid = int(candidate["older_revid"])
                    newer_revid = int(candidate["newer_revid"])
                    older_snapshot = fetch_revision_snapshot_fn(article=article, revid=older_revid, out_dir=out_dir / "pair_snapshots", python_cmd=py, repo_root=repo_root)
                    newer_snapshot = fetch_revision_snapshot_fn(article=article, revid=newer_revid, out_dir=out_dir / "pair_snapshots", python_cmd=py, repo_root=repo_root)
                    older_payload = dict(older_snapshot["snapshot_payload"])
                    newer_payload = dict(newer_snapshot["snapshot_payload"])
                    older_error = _snapshot_contract_error(article, older_payload)
                    newer_error = _snapshot_contract_error(article, newer_payload)
                    if older_error:
                        raise RuntimeError(older_error)
                    if newer_error:
                        raise RuntimeError(newer_error)
                    candidate.update(
                        _score_candidate_pair(
                            candidate,
                            older_snapshot_payload=older_payload,
                            newer_snapshot_payload=newer_payload,
                            section_focus_limit=history_cfg["section_focus_limit"],
                        )
                    )
                    candidate["selected"] = False
                    candidate["status"] = "candidate"
                    scored_candidates.append(candidate)
                    _emit_progress(
                        progress_callback,
                        "revision_pack_article_candidates_progress",
                        {
                            "section": "wiki_revision_candidates",
                            "completed": candidate_index,
                            "total": max(total_candidates, 1),
                            "article_id": article_id,
                            "message": f"Scored pair {candidate['pair_kind']} {older_revid}->{newer_revid}.",
                        },
                    )

                scored_candidates.sort(
                    key=lambda row: (
                        -float(row.get("candidate_score") or 0.0),
                        -int(row.get("newer_revid") or 0),
                        str(row.get("pair_kind") or ""),
                    )
                )
                candidate_pair_counts["considered"] += len(scored_candidates)

                selected_limit = min(len(scored_candidates), history_cfg["max_candidate_pairs"])
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_reports_started",
                    {
                        "section": "wiki_revision_reports",
                        "completed": 0,
                        "total": max(selected_limit, 1),
                        "article_id": article_id,
                        "message": f"Building up to {selected_limit} pair reports.",
                    },
                )
                for selected_index, candidate in enumerate(scored_candidates[: history_cfg["max_candidate_pairs"]], start=1):
                    selected = _build_pair_report(
                        article=article,
                        pair=dict(candidate),
                        out_dir=out_dir,
                        python_cmd=py,
                        repo_root=repo_root,
                        fetch_revision_snapshot_fn=fetch_revision_snapshot_fn,
                        build_timeline_fn=build_timeline_fn,
                        build_aoo_fn=build_aoo_fn,
                        auto_review_context_fn=auto_review_context_fn,
                        bridge_db_path=bridge_db_path,
                        section_focus_limit=history_cfg["section_focus_limit"],
                    )
                    selected_pairs.append(selected)
                    candidate_pair_counts["selected"] += 1
                    if selected.get("pair_report_path"):
                        candidate_pair_counts["reported"] += 1
                    _emit_progress(
                        progress_callback,
                        "revision_pack_article_reports_progress",
                        {
                            "section": "wiki_revision_reports",
                            "completed": selected_index,
                            "total": max(selected_limit, 1),
                            "article_id": article_id,
                            "message": f"Built pair report {selected.get('pair_id')}.",
                        },
                    )

                for candidate in scored_candidates:
                    materialized = next((row for row in selected_pairs if row["pair_id"] == candidate["pair_id"]), candidate)
                    _insert_candidate_pair(conn, run_id=run_id, article_id=article_id, pair_payload=materialized)

                if previous_revid is None:
                    current_timeline = build_timeline_fn(snapshot_path=current_snapshot_path, out_path=current_paths["timeline"], python_cmd=py, repo_root=repo_root)
                    current_aoo = build_aoo_fn(article=article, timeline_path=Path(str(current_timeline["timeline_path"])), out_path=current_paths["aoo"], python_cmd=py, repo_root=repo_root)
                    current_timeline_path = Path(str(current_timeline["timeline_path"]))
                    current_aoo_path = Path(str(current_aoo["aoo_path"]))

                status: str
                if selected_pairs:
                    status = "changed"
                elif previous_revid is None:
                    status = "baseline_initialized"
                elif current_revid == previous_revid:
                    status = "unchanged"
                else:
                    status = "no_candidate_delta"
                summary_counts[status] = summary_counts.get(status, 0) + 1

                top_severity = "none"
                packet_counts: dict[str, Any] = {}
                if selected_pairs:
                    for severity in ("high", "medium", "low"):
                        if any(pair.get("top_severity") == severity for pair in selected_pairs):
                            top_severity = severity
                            break
                    aggregate_counts = {"high": 0, "medium": 0, "low": 0}
                    for pair in selected_pairs:
                        for key, value in dict(pair.get("packet_counts") or {}).items():
                            aggregate_counts[key] = aggregate_counts.get(key, 0) + int(value)
                    packet_counts = aggregate_counts
                    current_report_path = Path(str(selected_pairs[0]["pair_report_path"])) if selected_pairs[0].get("pair_report_path") else None
                primary_pair = selected_pairs[0] if selected_pairs else None
                if _graph_enabled(pack, article) and selected_pairs:
                    contested_graph_path, contested_graph_payload = _build_contested_region_graph(
                        article=article,
                        run_id=run_id,
                        selected_pairs=selected_pairs,
                        out_dir=out_dir,
                    )
                    contested_graph_summary = dict((contested_graph_payload.get("summary") or {}))
                    _insert_contested_graph(
                        conn,
                        run_id=run_id,
                        article_id=article_id,
                        graph_path=contested_graph_path,
                        graph_payload=contested_graph_payload,
                    )
                    contested_graph_counts["articles_with_graphs"] += 1
                    contested_graph_counts["graphs_built"] += 1
                    contested_graph_counts["cycles_detected"] += int(contested_graph_summary.get("cycle_count") or 0)
                    contested_graph_counts["regions_detected"] += int(contested_graph_summary.get("region_count") or 0)

                result_payload = {
                    "article_id": article_id,
                    "title": article.get("title"),
                    "status": status,
                    "baseline_initialized": previous_revid is None,
                    "previous_revid": previous_revid,
                    "current_revid": current_revid,
                    "top_severity": top_severity,
                    "history_window": {
                        "max_revisions": history_cfg["max_revisions"],
                        "window_days": history_cfg["window_days"],
                        "fetched_row_count": len(history_rows),
                    },
                    "candidate_pairs_considered": len(scored_candidates),
                    "candidate_pairs_selected": len(selected_pairs),
                    "selected_pair_ids": [str(pair["pair_id"]) for pair in selected_pairs],
                    "selected_primary_pair_id": primary_pair["pair_id"] if primary_pair else None,
                    "selected_primary_pair_kind": primary_pair["pair_kind"] if primary_pair else None,
                    "selected_primary_pair_kinds": list(primary_pair.get("pair_kinds") or []) if primary_pair else [],
                    "selected_primary_pair_score": primary_pair["candidate_score"] if primary_pair else None,
                    "pair_reports": [
                        {
                            "pair_id": pair["pair_id"],
                            "pair_kind": pair["pair_kind"],
                            "pair_kinds": list(pair.get("pair_kinds") or []),
                            "older_revid": pair["older_revid"],
                            "newer_revid": pair["newer_revid"],
                            "candidate_score": pair["candidate_score"],
                            "pair_report_path": pair.get("pair_report_path"),
                            "top_severity": pair.get("top_severity", "none"),
                            "top_changed_sections": list(((pair.get("section_delta_summary") or {}).get("top_changed_sections")) or []),
                        }
                        for pair in selected_pairs
                    ],
                    "packet_counts": packet_counts,
                    "contested_graph_available": contested_graph_summary is not None,
                    "contested_graph_path": str(contested_graph_path) if contested_graph_path else None,
                    "contested_graph_summary": contested_graph_summary,
                    "report_path": str(current_report_path) if current_report_path else None,
                }

                _upsert_article_state(
                    conn,
                    article_id=article_id,
                    revid=current_revid,
                    rev_timestamp=_norm_text(current_snapshot_payload.get("rev_timestamp")) or None,
                    fetched_at=_norm_text(current_snapshot_payload.get("fetched_at")) or None,
                    snapshot_path=current_snapshot_path,
                    timeline_path=current_timeline_path or (Path(str(previous_state["timeline_path"])) if previous_state and previous_state["timeline_path"] else None),
                    aoo_path=current_aoo_path or (Path(str(previous_state["aoo_path"])) if previous_state and previous_state["aoo_path"] else None),
                    report_path=current_report_path or (Path(str(previous_state["report_path"])) if previous_state and previous_state["report_path"] else None),
                    status=status,
                )
                _insert_article_result(
                    conn,
                    run_id=run_id,
                    article_id=article_id,
                    status=status,
                    previous_revid=previous_revid,
                    current_revid=current_revid,
                    top_severity=top_severity,
                    packet_counts=packet_counts,
                    snapshot_path=current_snapshot_path,
                    timeline_path=current_timeline_path,
                    aoo_path=current_aoo_path,
                    report_path=current_report_path,
                    result_payload=result_payload,
                )
                replace_issue_packets(
                    conn,
                    run_id=run_id,
                    article_id=article_id,
                    packet_rows=_selected_issue_packet_rows(selected_pairs),
                )
                replace_selected_pairs(
                    conn,
                    run_id=run_id,
                    article_id=article_id,
                    pair_rows=_selected_pair_rows(selected_pairs),
                )
                article_results.append(result_payload)
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_finished",
                    {
                        "section": "wiki_revision_articles",
                        "completed": article_index,
                        "total": max(total_articles, 1),
                        "article_id": article_id,
                        "status": status,
                        "message": f"Finished {article.get('title')} with status {status}.",
                    },
                )
            except Exception as exc:
                status = "error"
                summary_counts[status] = summary_counts.get(status, 0) + 1
                result_payload = {
                    "article_id": article_id,
                    "title": article.get("title"),
                    "status": status,
                    "previous_revid": previous_revid,
                    "current_revid": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "contested_graph_available": False,
                    "contested_graph_path": None,
                    "contested_graph_summary": None,
                    "report_path": None,
                }
                _insert_article_result(
                    conn,
                    run_id=run_id,
                    article_id=article_id,
                    status=status,
                    previous_revid=previous_revid,
                    current_revid=None,
                    top_severity="none",
                    packet_counts={},
                    snapshot_path=current_snapshot_path,
                    timeline_path=current_timeline_path,
                    aoo_path=current_aoo_path,
                    report_path=current_report_path,
                    result_payload=result_payload,
                )
                replace_issue_packets(conn, run_id=run_id, article_id=article_id, packet_rows=[])
                replace_selected_pairs(conn, run_id=run_id, article_id=article_id, pair_rows=[])
                article_results.append(result_payload)
                _emit_progress(
                    progress_callback,
                    "revision_pack_article_finished",
                    {
                        "section": "wiki_revision_articles",
                        "completed": article_index,
                        "total": max(total_articles, 1),
                        "article_id": article_id,
                        "status": status,
                        "message": f"Failed {article.get('title')}: {type(exc).__name__}.",
                    },
                )

        summary = build_run_summary(
            schema_version=STATE_SCHEMA_VERSION,
            pack_id=pack_id,
            run_id=run_id,
            state_db_path=state_db_path,
            out_dir=out_dir,
            counts=summary_counts,
            candidate_pair_counts=candidate_pair_counts,
            contested_graph_counts=contested_graph_counts,
            article_results=article_results,
        )
        summary_path = out_dir / "runs" / f"{slug_artifact_name(run_id)}.json"
        write_json_file(summary_path, summary)
        summary["summary_path"] = str(summary_path)
        _emit_progress(
            progress_callback,
            "revision_pack_articles_finished",
            {
                "section": "wiki_revision_articles",
                "completed": len(article_results),
                "total": max(total_articles, 1),
                "status": "ok",
                "message": f"Processed {len(article_results)} article results.",
            },
        )
        completed_at = _utc_now_iso()
        _complete_run(conn, run_id=run_id, status="ok", summary=summary, completed_at=completed_at)
        upsert_run_summary(
            conn,
            run_id=run_id,
            pack_id=pack_id,
            started_at=run_started,
            completed_at=completed_at,
            status="ok",
            out_dir=str(out_dir),
            summary=summary,
        )
        replace_changed_articles(conn, run_id=run_id, pack_id=pack_id, article_rows=article_results)
        conn.commit()
        return summary


def human_summary(payload: Mapping[str, Any]) -> str:
    return _human_summary(payload)
