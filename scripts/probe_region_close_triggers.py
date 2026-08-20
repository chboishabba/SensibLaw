#!/usr/bin/env python3
"""Diagnose trigger-attached region-close work on an exact retained DB clone."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.region_close_trigger_probe import (  # noqa: E402
    build_template_clone,
    run_region_close_probe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    authority = parser.add_mutually_exclusive_group(required=True)
    authority.add_argument("--database-url")
    authority.add_argument("--clone-database-url")
    parser.add_argument(
        "--source-database",
        help="Required provenance when reusing an already-created exact clone.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scout-count", type=int, default=9)
    args = parser.parse_args()

    if args.clone_database_url:
        if not args.source_database:
            parser.error("--source-database is required with --clone-database-url")
        clone_url = args.clone_database_url
        provenance = {
            "source_database": args.source_database,
            "clone_database": str(
                conninfo_to_dict(clone_url).get("dbname") or "unknown"
            ),
            "clone_method": "postgresql-template-exact-reused",
        }
    else:
        clone_url, provenance = build_template_clone(args.database_url)
    report = run_region_close_probe(clone_url, scout_count=args.scout_count)
    report["provenance"] = {
        **provenance,
        "git_sha": subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip(),
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "provenance": provenance}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
