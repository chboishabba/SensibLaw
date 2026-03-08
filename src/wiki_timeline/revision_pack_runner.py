from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from src.wiki_timeline.revision_harness import build_revision_comparison_report

STATE_SCHEMA_VERSION = "wiki_revision_pack_state_v0_1"
_WS_RE = re.compile(r"\s+")


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

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


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _subprocess_json(args: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def _looks_like_person_title(title: str) -> bool:
    parts = [part for part in _norm_text(title).split(" ") if part]
    if len(parts) < 2 or len(parts) > 4:
        return False
    if any(part.lower() in {"language", "languages", "park", "system", "space", "alphabet"} for part in parts):
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
    return report


def _artifact_paths(*, out_dir: Path, article_id: str, revid: int | None) -> dict[str, Path]:
    revid_text = str(revid) if revid is not None else "none"
    base = f"{_slug(article_id)}__revid_{revid_text}"
    return {
        "snapshot": out_dir / "snapshots" / f"{base}.json",
        "timeline": out_dir / "timeline" / f"{base}.json",
        "aoo": out_dir / "aoo" / f"{base}.json",
        "report": out_dir / "reports" / f"{base}.json",
    }


def run(
    *,
    pack_path: Path,
    out_dir: Path,
    state_db_path: Path,
    bridge_db_path: Path | None = None,
    python_cmd: str | None = None,
    fetch_current_snapshot_fn: Callable[..., Mapping[str, Any]] | None = None,
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
    build_timeline_fn = build_timeline_fn or _default_build_timeline
    build_aoo_fn = build_aoo_fn or _default_build_aoo
    auto_review_context_fn = auto_review_context_fn or _default_auto_review_context

    article_results: list[dict[str, Any]] = []
    summary_counts = {"baseline_initialized": 0, "unchanged": 0, "changed": 0, "error": 0}

    with sqlite3.connect(str(state_db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_revision_pack_schema(conn)
        _store_pack_manifest(conn, pack_path=pack_path, pack=pack)
        _insert_run(conn, run_id=run_id, pack_id=pack_id, started_at=run_started, out_dir=out_dir)

        for article in pack.get("articles") or []:
            if not isinstance(article, Mapping):
                continue
            article_id = str(article.get("article_id") or "")
            current_snapshot_path: Path | None = None
            current_timeline_path: Path | None = None
            current_aoo_path: Path | None = None
            current_report_path: Path | None = None
            previous_state = _load_article_state(conn, article_id)
            previous_revid = int(previous_state["last_revid"]) if previous_state and previous_state["last_revid"] is not None else None
            try:
                fetched = fetch_current_snapshot_fn(article=article, out_dir=out_dir / "snapshots", python_cmd=py, repo_root=repo_root)
                current_snapshot_path = Path(str(fetched["snapshot_path"]))
                current_snapshot_payload = dict(fetched["snapshot_payload"])
                current_revid_raw = current_snapshot_payload.get("revid")
                current_revid = int(current_revid_raw) if current_revid_raw is not None else None
                artifact_paths = _artifact_paths(out_dir=out_dir, article_id=article_id, revid=current_revid)
                if current_snapshot_path != artifact_paths["snapshot"]:
                    _write_json(artifact_paths["snapshot"], current_snapshot_payload)
                    current_snapshot_path = artifact_paths["snapshot"]

                if previous_revid is None:
                    timeline = build_timeline_fn(snapshot_path=current_snapshot_path, out_path=artifact_paths["timeline"], python_cmd=py, repo_root=repo_root)
                    aoo = build_aoo_fn(article=article, timeline_path=Path(str(timeline["timeline_path"])), out_path=artifact_paths["aoo"], python_cmd=py, repo_root=repo_root)
                    current_timeline_path = Path(str(timeline["timeline_path"]))
                    current_aoo_path = Path(str(aoo["aoo_path"]))
                    status = "baseline_initialized"
                    summary_counts[status] += 1
                    result_payload = {
                        "article_id": article_id,
                        "title": article.get("title"),
                        "status": status,
                        "previous_revid": None,
                        "current_revid": current_revid,
                        "report_path": None,
                    }
                    _upsert_article_state(
                        conn,
                        article_id=article_id,
                        revid=current_revid,
                        rev_timestamp=_norm_text(current_snapshot_payload.get("rev_timestamp")) or None,
                        fetched_at=_norm_text(current_snapshot_payload.get("fetched_at")) or None,
                        snapshot_path=current_snapshot_path,
                        timeline_path=current_timeline_path,
                        aoo_path=current_aoo_path,
                        report_path=None,
                        status=status,
                    )
                    _insert_article_result(
                        conn,
                        run_id=run_id,
                        article_id=article_id,
                        status=status,
                        previous_revid=None,
                        current_revid=current_revid,
                        top_severity="none",
                        packet_counts={},
                        snapshot_path=current_snapshot_path,
                        timeline_path=current_timeline_path,
                        aoo_path=current_aoo_path,
                        report_path=None,
                        result_payload=result_payload,
                    )
                    article_results.append(result_payload)
                    continue

                if current_revid == previous_revid:
                    status = "unchanged"
                    summary_counts[status] += 1
                    result_payload = {
                        "article_id": article_id,
                        "title": article.get("title"),
                        "status": status,
                        "previous_revid": previous_revid,
                        "current_revid": current_revid,
                        "report_path": previous_state["report_path"] if previous_state else None,
                    }
                    _upsert_article_state(
                        conn,
                        article_id=article_id,
                        revid=current_revid,
                        rev_timestamp=_norm_text(current_snapshot_payload.get("rev_timestamp")) or None,
                        fetched_at=_norm_text(current_snapshot_payload.get("fetched_at")) or None,
                        snapshot_path=current_snapshot_path,
                        timeline_path=Path(str(previous_state["timeline_path"])) if previous_state and previous_state["timeline_path"] else None,
                        aoo_path=Path(str(previous_state["aoo_path"])) if previous_state and previous_state["aoo_path"] else None,
                        report_path=Path(str(previous_state["report_path"])) if previous_state and previous_state["report_path"] else None,
                        status=status,
                    )
                    _insert_article_result(
                        conn,
                        run_id=run_id,
                        article_id=article_id,
                        status=status,
                        previous_revid=previous_revid,
                        current_revid=current_revid,
                        top_severity="none",
                        packet_counts={},
                        snapshot_path=current_snapshot_path,
                        timeline_path=Path(str(previous_state["timeline_path"])) if previous_state and previous_state["timeline_path"] else None,
                        aoo_path=Path(str(previous_state["aoo_path"])) if previous_state and previous_state["aoo_path"] else None,
                        report_path=Path(str(previous_state["report_path"])) if previous_state and previous_state["report_path"] else None,
                        result_payload=result_payload,
                    )
                    article_results.append(result_payload)
                    continue

                timeline = build_timeline_fn(snapshot_path=current_snapshot_path, out_path=artifact_paths["timeline"], python_cmd=py, repo_root=repo_root)
                aoo = build_aoo_fn(article=article, timeline_path=Path(str(timeline["timeline_path"])), out_path=artifact_paths["aoo"], python_cmd=py, repo_root=repo_root)
                current_timeline_path = Path(str(timeline["timeline_path"]))
                current_aoo_path = Path(str(aoo["aoo_path"]))

                previous_snapshot_payload = _read_json(Path(str(previous_state["snapshot_path"]))) if previous_state and previous_state["snapshot_path"] else None
                previous_aoo_payload = _read_json(Path(str(previous_state["aoo_path"]))) if previous_state and previous_state["aoo_path"] else None
                current_aoo_payload = _read_json(current_aoo_path)
                report = build_revision_comparison_report(
                    previous_snapshot=previous_snapshot_payload,
                    current_snapshot=current_snapshot_payload,
                    previous_payload=previous_aoo_payload,
                    current_payload=current_aoo_payload,
                )
                report = _merge_packet_review_context(
                    report=report,
                    article=article,
                    auto_review_context_fn=auto_review_context_fn,
                    bridge_db_path=bridge_db_path,
                )
                current_report_path = artifact_paths["report"]
                _write_json(current_report_path, report)
                status = "changed"
                summary_counts[status] += 1
                top_severity = str(((report.get("triage_dashboard") or {}).get("highest_severity")) or "none")
                packet_counts = dict(((report.get("triage_dashboard") or {}).get("packet_counts")) or {})
                result_payload = {
                    "article_id": article_id,
                    "title": article.get("title"),
                    "status": status,
                    "previous_revid": previous_revid,
                    "current_revid": current_revid,
                    "report_path": str(current_report_path),
                    "top_severity": top_severity,
                }
                _upsert_article_state(
                    conn,
                    article_id=article_id,
                    revid=current_revid,
                    rev_timestamp=_norm_text(current_snapshot_payload.get("rev_timestamp")) or None,
                    fetched_at=_norm_text(current_snapshot_payload.get("fetched_at")) or None,
                    snapshot_path=current_snapshot_path,
                    timeline_path=current_timeline_path,
                    aoo_path=current_aoo_path,
                    report_path=current_report_path,
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
                summary_counts[status] += 1
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
            "highest_severity": highest_severity,
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
    lines = [
        f"pack={payload.get('pack_id')} run={payload.get('run_id')}",
        (
            "counts: "
            f"baseline_initialized={counts.get('baseline_initialized', 0)} "
            f"unchanged={counts.get('unchanged', 0)} "
            f"changed={counts.get('changed', 0)} "
            f"error={counts.get('error', 0)}"
        ),
        f"highest_severity={payload.get('highest_severity')}",
    ]
    for row in payload.get("articles") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"{row.get('article_id')}: status={row.get('status')} prev={row.get('previous_revid')} curr={row.get('current_revid')} report={row.get('report_path')}"
        )
    return "\n".join(lines)
