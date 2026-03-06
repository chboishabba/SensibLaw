#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report tokenizer/compression + structure stats for the isolated chat test DB.")
    parser.add_argument("--db-path", default=".cache_local/itir_chat_test.sqlite")
    parser.add_argument("--run-id")
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.reporting.structure_report import build_structure_report, load_chat_units  # noqa: PLC0415

    db_path = Path(args.db_path).expanduser().resolve()
    units = load_chat_units(db_path, args.run_id)
    report = build_structure_report(units, top_n=args.top_n)
    payload = {
        "db_path": str(db_path),
        "run_id": args.run_id or (units[0].source_id if units else None),
        "message_count": report["unit_count"],
        **report,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
