#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Import legacy wiki_timeline_*_aoo.json artifacts into the canonical SQLite store.")
    p.add_argument("--json-path", required=True, help="Path to a wiki_timeline_*_aoo.json artifact.")
    p.add_argument(
        "--db-path",
        default="SensibLaw/.cache_local/wiki_timeline_aoo.sqlite",
        help="Output DB path (default: SensibLaw/.cache_local/wiki_timeline_aoo.sqlite).",
    )
    args = p.parse_args()

    json_path = Path(args.json_path).expanduser().resolve()
    if not json_path.exists():
        raise SystemExit(f"JSON artifact not found: {json_path}")

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Expected top-level JSON object payload")

    # Best-effort: use the declared source_timeline.path as the timeline_path input.
    # (If it no longer exists, the persistence layer falls back to hashing the path string.)
    src_tl = payload.get("source_timeline") if isinstance(payload.get("source_timeline"), dict) else {}
    tl_path_raw = str(src_tl.get("path") or "").strip()
    tl_path = Path(tl_path_raw) if tl_path_raw else None

    prof_path = None
    # Some exports may include a profile path; tolerate its absence.
    prof_raw = payload.get("extraction_profile_path")
    if isinstance(prof_raw, str) and prof_raw.strip():
        prof_path = Path(prof_raw.strip())

    db_path = Path(args.db_path).expanduser().resolve()

    # Script is typically run from repo root; make SensibLaw/ importable as `src.*`.
    sb_root = Path(__file__).resolve().parents[1]
    if str(sb_root) not in sys.path:
        sys.path.insert(0, str(sb_root))

    from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run  # noqa: PLC0415

    res = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=payload,
        timeline_path=tl_path,
        candidates_path=None,
        profile_path=prof_path,
        extractor_path=Path(__file__),
    )

    print(json.dumps({"ok": True, "db_path": str(db_path), "run_id": res.run_id, "events": res.n_events}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
