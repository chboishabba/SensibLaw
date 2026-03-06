#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


REQUIRED_SUFFIXES = [
    "wiki_timeline_gwb.json",
    "wiki_timeline_gwb_public_bios_v1.json",
    "wiki_timeline_hca_s942025_aoo.json",
    "wiki_timeline_legal_principles_au_v1.json",
    "wiki_timeline_legal_principles_au_v1_follow.json",
]


def _pick_best_run(conn: sqlite3.Connection, suffix: str) -> str | None:
    row = conn.execute(
        """
        SELECT run_id
        FROM wiki_timeline_aoo_runs
        WHERE timeline_path LIKE ?
        ORDER BY generated_at DESC, n_events DESC, run_id ASC
        LIMIT 1
        """,
        (f"%{suffix}",),
    ).fetchone()
    return str(row["run_id"]) if row else None


def main() -> None:
    p = argparse.ArgumentParser(description="Eagerly rewrite wiki timeline runs into the canonical ITIR DB.")
    p.add_argument("--source-db", default="SensibLaw/.cache_local/wiki_timeline_aoo.sqlite")
    p.add_argument("--dest-db", default=".cache_local/itir.sqlite")
    p.add_argument("--artifact-json", action="append", default=[])
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from SensibLaw.src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run  # noqa: PLC0415

    source_db = Path(args.source_db).expanduser()
    dest_db = Path(args.dest_db).expanduser()
    dest_db.parent.mkdir(parents=True, exist_ok=True)

    migrated_runs: list[dict[str, object]] = []

    if source_db.exists():
        with sqlite3.connect(str(source_db)) as source_conn:
            source_conn.row_factory = sqlite3.Row
            run_ids = [str(r["run_id"]) for r in source_conn.execute("SELECT run_id FROM wiki_timeline_aoo_runs ORDER BY generated_at, run_id")]
            for run_id in run_ids:
                payload = load_run_payload_from_normalized(source_conn, run_id)
                if not payload:
                    continue
                src_timeline = payload.get("source_timeline") if isinstance(payload.get("source_timeline"), dict) else {}
                timeline_path_raw = str(src_timeline.get("path") or "").strip()
                timeline_path = Path(timeline_path_raw) if timeline_path_raw else None
                if timeline_path is not None and not timeline_path.is_absolute():
                    timeline_path = (repo_root / timeline_path).resolve()
                if timeline_path is not None and not timeline_path.exists():
                    timeline_path = None
                try:
                    res = persist_wiki_timeline_aoo_run(
                        db_path=dest_db,
                        out_payload=payload,
                        timeline_path=timeline_path,
                        candidates_path=None,
                        profile_path=None,
                        extractor_path=Path(__file__).resolve(),
                        run_id_override=run_id,
                    )
                except Exception as exc:
                    raise SystemExit(f"failed migrating run_id={run_id} timeline_path={timeline_path}: {exc}") from exc
                migrated_runs.append({"run_id": res.run_id, "events": res.n_events, "source": "source_db"})

    for artifact in args.artifact_json:
        artifact_path = Path(artifact).expanduser()
        if not artifact_path.exists():
            continue
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        src_timeline = payload.get("source_timeline") if isinstance(payload.get("source_timeline"), dict) else {}
        timeline_path_raw = str(src_timeline.get("path") or "").strip()
        timeline_path = Path(timeline_path_raw) if timeline_path_raw else artifact_path
        if not timeline_path.is_absolute():
            timeline_path = (repo_root / timeline_path).resolve()
        if not timeline_path.exists():
            timeline_path = artifact_path
        res = persist_wiki_timeline_aoo_run(
            db_path=dest_db,
            out_payload=payload,
            timeline_path=timeline_path,
            candidates_path=None,
            profile_path=None,
            extractor_path=Path(__file__).resolve(),
        )
        migrated_runs.append({"run_id": res.run_id, "events": res.n_events, "source": str(artifact_path)})

    with sqlite3.connect(str(dest_db)) as conn:
        conn.row_factory = sqlite3.Row
        missing_suffixes = [suffix for suffix in REQUIRED_SUFFIXES if _pick_best_run(conn, suffix) is None]

    print(
        json.dumps(
            {
                "ok": len(missing_suffixes) == 0,
                "dest_db": str(dest_db),
                "migrated_run_count": len(migrated_runs),
                "missing_suffixes": missing_suffixes,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if missing_suffixes:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
