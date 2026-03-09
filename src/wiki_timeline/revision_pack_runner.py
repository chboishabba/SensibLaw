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

STATE_SCHEMA_VERSION = "wiki_revision_pack_state_v0_2"
PAIR_REPORT_SCHEMA_VERSION = "wiki_revision_pair_report_v0_1"
_WS_RE = re.compile(r"\s+")
_SECTION_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.MULTILINE)
_REVERT_RE = re.compile(r"\b(revert|reverted|reverting|undid|undo|rv|rollback)\b", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _slug(text: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(text or "").strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("._") or "artifact"


def _norm_text(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_out_dir_for_pack(pack_path: Path) -> Path:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack_id = str(pack.get("pack_id") or pack_path.stem or "wiki_revision_monitor").strip()
    return Path("SensibLaw/demo/ingest/wiki_revision_monitor") / _slug(pack_id)


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_runs (
          run_id TEXT PRIMARY KEY,
          pack_id TEXT NOT NULL REFERENCES wiki_revision_monitor_packs(pack_id) ON DELETE CASCADE,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          status TEXT NOT NULL,
          out_dir TEXT NOT NULL,
          summary_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_article_results (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          status TEXT NOT NULL,
          previous_revid INTEGER,
          current_revid INTEGER,
          top_severity TEXT NOT NULL,
          packet_counts_json TEXT NOT NULL,
          snapshot_path TEXT,
          timeline_path TEXT,
          aoo_path TEXT,
          report_path TEXT,
          result_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id)
        )
        """
    )
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_revision_monitor_candidate_pairs (
          run_id TEXT NOT NULL REFERENCES wiki_revision_monitor_runs(run_id) ON DELETE CASCADE,
          article_id TEXT NOT NULL REFERENCES wiki_revision_monitor_articles(article_id) ON DELETE CASCADE,
          pair_id TEXT NOT NULL,
          pair_kind TEXT NOT NULL,
          older_revid INTEGER,
          newer_revid INTEGER,
          selected INTEGER NOT NULL DEFAULT 0,
          score REAL NOT NULL DEFAULT 0,
          score_json TEXT NOT NULL,
          section_delta_json TEXT NOT NULL,
          pair_report_path TEXT,
          status TEXT NOT NULL,
          result_json TEXT NOT NULL,
          PRIMARY KEY (run_id, article_id, pair_id)
        )
        """
    )


def _store_pack_manifest(conn: sqlite3.Connection, *, pack_path: Path, pack: Mapping[str, Any]) -> None:
    ensure_revision_pack_schema(conn)
    pack_id = str(pack.get("pack_id") or "").strip()
    manifest_json = _stable_json(pack)
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
        INSERT INTO wiki_revision_monitor_runs(run_id, pack_id, started_at, completed_at, status, out_dir, summary_json)
        VALUES(?,?,?,?,?,?,?)
        """,
        (run_id, pack_id, started_at, None, "running", str(out_dir), "{}"),
    )


def _complete_run(conn: sqlite3.Connection, *, run_id: str, status: str, summary: Mapping[str, Any]) -> None:
    conn.execute(
        """
        UPDATE wiki_revision_monitor_runs
        SET completed_at = ?, status = ?, summary_json = ?
        WHERE run_id = ?
        """,
        (_utc_now_iso(), status, json.dumps(summary, sort_keys=True), run_id),
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
          run_id, article_id, status, previous_revid, current_revid, top_severity, packet_counts_json,
          snapshot_path, timeline_path, aoo_path, report_path, result_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            article_id,
            status,
            previous_revid,
            current_revid,
            top_severity,
            json.dumps(packet_counts, sort_keys=True),
            str(snapshot_path) if snapshot_path else None,
            str(timeline_path) if timeline_path else None,
            str(aoo_path) if aoo_path else None,
            str(report_path) if report_path else None,
            json.dumps(result_payload, sort_keys=True),
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
          score_json, section_delta_json, pair_report_path, status, result_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            json.dumps(pair_payload.get("score_breakdown") or {}, sort_keys=True),
            json.dumps(pair_payload.get("section_delta_summary") or {}, sort_keys=True),
            str(pair_payload.get("pair_report_path") or "") or None,
            str(pair_payload.get("status") or "candidate"),
            json.dumps(pair_payload, sort_keys=True),
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
    snapshot_payload = _read_json(snapshot_path)
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
    snapshot_payload = _read_json(snapshot_path)
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
    history_payload = _read_json(history_path)
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
    payload = _read_json(out_path)
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
    payload = _read_json(out_path)
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


def _artifact_paths(*, out_dir: Path, article_id: str, revid: int | None) -> dict[str, Path]:
    revid_text = str(revid) if revid is not None else "none"
    base = f"{_slug(article_id)}__revid_{revid_text}"
    return {
        "snapshot": out_dir / "snapshots" / f"{base}.json",
        "timeline": out_dir / "timeline" / f"{base}.json",
        "aoo": out_dir / "aoo" / f"{base}.json",
    }


def _pair_artifact_paths(*, out_dir: Path, article_id: str, pair_kind: str, older_revid: int | None, newer_revid: int | None) -> dict[str, Path]:
    base = f"{_slug(article_id)}__{_slug(pair_kind)}__{older_revid or 'none'}__{newer_revid or 'none'}"
    return {
        "older_snapshot": out_dir / "pair_snapshots" / f"{base}__older.json",
        "newer_snapshot": out_dir / "pair_snapshots" / f"{base}__newer.json",
        "older_timeline": out_dir / "timeline" / f"{base}__older.json",
        "newer_timeline": out_dir / "timeline" / f"{base}__newer.json",
        "older_aoo": out_dir / "aoo" / f"{base}__older.json",
        "newer_aoo": out_dir / "aoo" / f"{base}__newer.json",
        "pair_report": out_dir / "pair_reports" / f"{base}.json",
    }


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


def _severity_rank(value: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1, "none": 0}.get(str(value or "none"), 0)


def _build_pack_triage(article_results: list[dict[str, Any]], *, article_limit: int = 5, pair_limit: int = 8, section_limit: int = 10) -> dict[str, Any]:
    top_articles: list[dict[str, Any]] = []
    top_pairs: list[dict[str, Any]] = []
    top_sections: dict[str, dict[str, Any]] = {}

    for row in article_results:
        if not isinstance(row, Mapping):
            continue
        top_articles.append(
            {
                "article_id": row.get("article_id"),
                "title": row.get("title"),
                "status": row.get("status"),
                "top_severity": row.get("top_severity", "none"),
                "selected_primary_pair_kind": row.get("selected_primary_pair_kind"),
                "selected_primary_pair_id": row.get("selected_primary_pair_id"),
                "selected_primary_pair_score": row.get("selected_primary_pair_score"),
                "candidate_pairs_selected": row.get("candidate_pairs_selected", 0),
                "report_path": row.get("report_path"),
            }
        )
        for pair in row.get("pair_reports") or []:
            if not isinstance(pair, Mapping):
                continue
            top_pairs.append(
                {
                    "article_id": row.get("article_id"),
                    "title": row.get("title"),
                    "pair_id": pair.get("pair_id"),
                    "pair_kind": pair.get("pair_kind"),
                    "pair_kinds": list(pair.get("pair_kinds") or []),
                    "older_revid": pair.get("older_revid"),
                    "newer_revid": pair.get("newer_revid"),
                    "candidate_score": pair.get("candidate_score"),
                    "top_severity": pair.get("top_severity", "none"),
                    "pair_report_path": pair.get("pair_report_path"),
                }
            )
            for section in pair.get("top_changed_sections") or []:
                if not isinstance(section, Mapping):
                    continue
                name = str(section.get("section") or "").strip()
                if not name:
                    continue
                touched = int(section.get("touched_bytes") or 0)
                existing = top_sections.get(name)
                candidate = {
                    "section": name,
                    "max_touched_bytes": touched,
                    "article_id": row.get("article_id"),
                    "title": row.get("title"),
                    "pair_id": pair.get("pair_id"),
                    "pair_kind": pair.get("pair_kind"),
                    "top_severity": pair.get("top_severity", "none"),
                    "pair_report_path": pair.get("pair_report_path"),
                }
                if existing is None or touched > int(existing.get("max_touched_bytes") or 0):
                    top_sections[name] = candidate

    top_articles.sort(
        key=lambda item: (
            -_severity_rank(item.get("top_severity")),
            -float(item.get("selected_primary_pair_score") or 0.0),
            -int(item.get("candidate_pairs_selected") or 0),
            str(item.get("article_id") or ""),
        )
    )
    top_pairs.sort(
        key=lambda item: (
            -_severity_rank(item.get("top_severity")),
            -float(item.get("candidate_score") or 0.0),
            str(item.get("article_id") or ""),
            str(item.get("pair_id") or ""),
        )
    )
    ranked_sections = sorted(
        top_sections.values(),
        key=lambda item: (
            -int(item.get("max_touched_bytes") or 0),
            -_severity_rank(item.get("top_severity")),
            str(item.get("section") or ""),
        ),
    )
    return {
        "top_changed_articles": top_articles[:article_limit],
        "top_high_severity_pairs": top_pairs[:pair_limit],
        "top_sections_changed": ranked_sections[:section_limit],
    }


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
    pair_paths = _pair_artifact_paths(out_dir=out_dir, article_id=str(article.get("article_id") or ""), pair_kind=str(pair["pair_kind"]), older_revid=older_revid, newer_revid=newer_revid)

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
    _write_json(pair_paths["older_snapshot"], older_snapshot_payload)
    _write_json(pair_paths["newer_snapshot"], newer_snapshot_payload)

    scoring = _score_candidate_pair(pair, older_snapshot_payload=older_snapshot_payload, newer_snapshot_payload=newer_snapshot_payload, section_focus_limit=section_focus_limit)
    pair.update(scoring)

    older_timeline = build_timeline_fn(snapshot_path=pair_paths["older_snapshot"], out_path=pair_paths["older_timeline"], python_cmd=python_cmd, repo_root=repo_root)
    newer_timeline = build_timeline_fn(snapshot_path=pair_paths["newer_snapshot"], out_path=pair_paths["newer_timeline"], python_cmd=python_cmd, repo_root=repo_root)
    older_aoo = build_aoo_fn(article=article, timeline_path=Path(str(older_timeline["timeline_path"])), out_path=pair_paths["older_aoo"], python_cmd=python_cmd, repo_root=repo_root)
    newer_aoo = build_aoo_fn(article=article, timeline_path=Path(str(newer_timeline["timeline_path"])), out_path=pair_paths["newer_aoo"], python_cmd=python_cmd, repo_root=repo_root)
    older_aoo_payload = _read_json(Path(str(older_aoo["aoo_path"])))
    newer_aoo_payload = _read_json(Path(str(newer_aoo["aoo_path"])))

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
    _write_json(pair_paths["pair_report"], wrapper)
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

    with sqlite3.connect(str(state_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_revision_pack_schema(conn)
        _store_pack_manifest(conn, pack_path=pack_path, pack=pack)
        _insert_run(conn, run_id=run_id, pack_id=pack_id, started_at=run_started, out_dir=out_dir)

        for article in pack.get("articles") or []:
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

            try:
                fetched = fetch_current_snapshot_fn(article=article, out_dir=out_dir / "snapshots", python_cmd=py, repo_root=repo_root)
                current_snapshot_path = Path(str(fetched["snapshot_path"]))
                current_snapshot_payload = dict(fetched["snapshot_payload"])
                contract_error = _snapshot_contract_error(article, current_snapshot_payload)
                if contract_error:
                    raise RuntimeError(contract_error)
                current_revid = _safe_int(current_snapshot_payload.get("revid"))
                current_paths = _artifact_paths(out_dir=out_dir, article_id=article_id, revid=current_revid)
                if current_snapshot_path != current_paths["snapshot"]:
                    _write_json(current_paths["snapshot"], current_snapshot_payload)
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

                selected_pairs: list[dict[str, Any]] = []
                candidates = _candidate_pairs(history_rows, previous_state, current_revid)
                scored_candidates: list[dict[str, Any]] = []
                for candidate in candidates:
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

                scored_candidates.sort(
                    key=lambda row: (
                        -float(row.get("candidate_score") or 0.0),
                        -int(row.get("newer_revid") or 0),
                        str(row.get("pair_kind") or ""),
                    )
                )
                candidate_pair_counts["considered"] += len(scored_candidates)

                for candidate in scored_candidates[: history_cfg["max_candidate_pairs"]]:
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
                article_results.append(result_payload)
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
                article_results.append(result_payload)

        highest_severity = "none"
        for candidate in ("high", "medium", "low"):
            if any(row.get("top_severity") == candidate for row in article_results):
                highest_severity = candidate
                break
        summary = {
            "schema_version": STATE_SCHEMA_VERSION,
            "ok": True,
            "pack_id": pack_id,
            "run_id": run_id,
            "state_db_path": str(state_db_path),
            "out_dir": str(out_dir),
            "counts": summary_counts,
            "candidate_pair_counts": candidate_pair_counts,
            "highest_severity": highest_severity,
            "pack_triage": _build_pack_triage(article_results),
            "articles": article_results,
        }
        summary_path = out_dir / "runs" / f"{_slug(run_id)}.json"
        _write_json(summary_path, summary)
        summary["summary_path"] = str(summary_path)
        _complete_run(conn, run_id=run_id, status="ok", summary=summary)
        conn.commit()
        return summary


def human_summary(payload: Mapping[str, Any]) -> str:
    counts = payload.get("counts") or {}
    pair_counts = payload.get("candidate_pair_counts") or {}
    lines = [
        f"pack={payload.get('pack_id')} run={payload.get('run_id')}",
        (
            "counts: "
            f"baseline_initialized={counts.get('baseline_initialized', 0)} "
            f"unchanged={counts.get('unchanged', 0)} "
            f"changed={counts.get('changed', 0)} "
            f"no_candidate_delta={counts.get('no_candidate_delta', 0)} "
            f"error={counts.get('error', 0)}"
        ),
        (
            "pairs: "
            f"considered={pair_counts.get('considered', 0)} "
            f"selected={pair_counts.get('selected', 0)} "
            f"reported={pair_counts.get('reported', 0)}"
        ),
        f"highest_severity={payload.get('highest_severity')}",
    ]
    triage = payload.get("pack_triage") or {}
    top_articles = triage.get("top_changed_articles") or []
    top_pairs = triage.get("top_high_severity_pairs") or []
    top_sections = triage.get("top_sections_changed") or []
    if top_articles:
        lines.append(
            "top_articles="
            + ", ".join(
                f"{row.get('article_id')}:{row.get('top_severity')}:{row.get('selected_primary_pair_kind')}"
                for row in top_articles[:3]
                if isinstance(row, Mapping)
            )
        )
    if top_pairs:
        lines.append(
            "top_pairs="
            + ", ".join(
                f"{row.get('article_id')}:{row.get('pair_kind')}:{row.get('top_severity')}"
                for row in top_pairs[:3]
                if isinstance(row, Mapping)
            )
        )
    if top_sections:
        lines.append(
            "top_sections="
            + ", ".join(
                f"{row.get('section')}:{row.get('max_touched_bytes')}"
                for row in top_sections[:3]
                if isinstance(row, Mapping)
            )
        )
    for row in payload.get("articles") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"{row.get('article_id')}: status={row.get('status')} sev={row.get('top_severity', 'none')} prev={row.get('previous_revid')} curr={row.get('current_revid')} primary_pair={row.get('selected_primary_pair_kind')} pairs={row.get('candidate_pairs_selected', 0)} report={row.get('report_path')}"
        )
    return "\n".join(lines)
