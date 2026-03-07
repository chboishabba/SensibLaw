#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _resolve_db_path(raw: str | None) -> Path:
    return Path(raw or ".cache_local/itir.sqlite").expanduser().resolve()


def main() -> None:
    ap = argparse.ArgumentParser(description="Import, run, and report deterministic GWB U.S.-law linkage over the canonical ITIR DB.")
    ap.add_argument("--db-path", help="Canonical ITIR sqlite database path.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import-seed", help="Import reviewed GWB U.S.-law seed JSON into the shared DB.")
    imp.add_argument("--file", default="SensibLaw/data/ontology/gwb_us_law_linkage_seed_v1.json")

    run = sub.add_parser("run", help="Run deterministic linkage matching against the GWB timeline.")
    run.add_argument("--run-id")
    run.add_argument("--timeline-suffix", default="wiki_timeline_gwb.json")

    report = sub.add_parser("report", help="Emit deterministic linkage report for a matched run.")
    report.add_argument("--run-id")
    report.add_argument("--timeline-suffix", default="wiki_timeline_gwb.json")

    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.gwb_us_law.linkage import (  # noqa: PLC0415
        build_gwb_us_law_linkage_report,
        ensure_gwb_us_law_schema,
        import_gwb_us_law_seed_payload,
        run_gwb_us_law_linkage,
    )

    db_path = _resolve_db_path(args.db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_us_law_schema(conn)
        if args.cmd == "import-seed":
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            result = import_gwb_us_law_seed_payload(conn, payload)
            conn.commit()
            print(json.dumps({"ok": True, "db": str(db_path), **result}, indent=2, sort_keys=True))
            return
        if args.cmd == "run":
            result = run_gwb_us_law_linkage(conn, run_id=args.run_id, timeline_suffix=args.timeline_suffix)
            conn.commit()
            print(json.dumps({"ok": True, "db": str(db_path), **result}, indent=2, sort_keys=True))
            return
        result = run_gwb_us_law_linkage(conn, run_id=args.run_id, timeline_suffix=args.timeline_suffix)
        conn.commit()
        payload = build_gwb_us_law_linkage_report(conn, run_id=str(result["run_id"]))
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
