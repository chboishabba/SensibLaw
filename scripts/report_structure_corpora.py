#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report deterministic legal + operational structure across chat/context/transcript/shell corpora.")
    parser.add_argument("--chat-db")
    parser.add_argument("--messenger-db")
    parser.add_argument("--run-id")
    parser.add_argument("--context-file", action="append", default=[])
    parser.add_argument("--transcript-file", action="append", default=[])
    parser.add_argument("--shell-log", action="append", default=[])
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--by-source", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))
    from src.reporting.structure_report import (  # noqa: PLC0415
        build_structure_report,
        build_source_comparison_report,
        emit_comparison_summary,
        emit_human_summary,
        load_chat_units,
        load_file_units,
        load_messenger_units,
    )

    units = []
    if args.chat_db:
        units.extend(load_chat_units(args.chat_db, args.run_id))
    if args.messenger_db:
        units.extend(load_messenger_units(args.messenger_db, args.run_id))
    for path in args.context_file:
        units.extend(load_file_units(path, "context_file"))
    for path in args.transcript_file:
        units.extend(load_file_units(path, "transcript_file"))
    for path in args.shell_log:
        units.extend(load_file_units(path, "shell_log"))
    if not units:
        raise SystemExit("no corpus inputs provided")
    report = (
        build_source_comparison_report(units, top_n=args.top_n)
        if args.by_source
        else build_structure_report(units, top_n=args.top_n)
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if args.by_source:
        print(emit_comparison_summary(report, top_n=min(args.top_n, 5)))
        print("")
        print("overall")
        print(emit_human_summary(report["overall"], top_n=args.top_n))
        print("")
        for row in report["per_source"]:
            print(f"source={row['source_id']} type={row['source_type']}")
            print(emit_human_summary(row, top_n=args.top_n))
            print("")
        return
    print(emit_human_summary(report, top_n=args.top_n))


if __name__ == "__main__":
    main()
