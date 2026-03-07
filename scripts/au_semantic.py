#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/report the deterministic Australian semantic pipeline.")
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    sub = parser.add_subparsers(dest="cmd", required=True)

    import_p = sub.add_parser("import-seed")
    import_p.add_argument("--seed-path", default="")

    run_p = sub.add_parser("run")
    run_p.add_argument("--timeline-suffix", default="wiki_timeline_hca_s942025_aoo.json")
    run_p.add_argument("--run-id", default="")

    report_p = sub.add_parser("report")
    report_p.add_argument("--timeline-suffix", default="wiki_timeline_hca_s942025_aoo.json")
    report_p.add_argument("--run-id", default="")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.au_semantic.linkage import import_au_semantic_seed_payload  # noqa: PLC0415
    from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline  # noqa: PLC0415
    from src.gwb_us_law.semantic import ensure_gwb_semantic_schema  # noqa: PLC0415

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        if args.cmd == "import-seed":
            seed_path = Path(args.seed_path) if args.seed_path else sensiblaw_root / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
            payload = import_au_semantic_seed_payload(conn, json.loads(seed_path.read_text(encoding="utf-8")))
        elif args.cmd == "run":
            payload = run_au_semantic_pipeline(
                conn,
                timeline_suffix=args.timeline_suffix,
                run_id=args.run_id or None,
            )
        else:
            if args.run_id:
                active_run_id = args.run_id
            else:
                run_payload = run_au_semantic_pipeline(
                    conn,
                    timeline_suffix=args.timeline_suffix,
                    run_id=None,
                )
                active_run_id = str(run_payload["run_id"])
            payload = build_au_semantic_report(conn, run_id=active_run_id)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
