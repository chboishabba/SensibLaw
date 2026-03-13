#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.reporting.notebooklm_activity import (  # noqa: E402
    build_notebooklm_activity_report,
    list_notebooklm_activity_dates,
    query_notebooklm_activity_events,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query NotebookLM interaction observations from SB runs.")
    parser.add_argument("--runs-root", required=True, help="Path to StatiBaker runs root")
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD lower bound")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD upper bound")
    parser.add_argument("--notebook-id-hash", default=None, help="Optional notebook hash filter")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dates", help="List NotebookLM interaction date coverage")
    summary_parser = subparsers.add_parser("summary", help="Build NotebookLM interaction summary")
    summary_parser.add_argument("--event-limit", type=int, default=50, help="Max recent events in report")
    events_parser = subparsers.add_parser("events", help="Query recent NotebookLM interaction events")
    events_parser.add_argument("--event", default=None, help="Optional event filter")
    events_parser.add_argument("--text-query", default=None, help="Optional case-insensitive text filter")
    events_parser.add_argument("--limit", type=int, default=50, help="Max rows to return")
    args = parser.parse_args()

    runs_root = Path(args.runs_root).expanduser().resolve()
    if args.command == "dates":
        payload = {"dates": list_notebooklm_activity_dates(runs_root, start_date=args.start_date, end_date=args.end_date)}
    elif args.command == "summary":
        payload = {
            "report": build_notebooklm_activity_report(
                runs_root,
                start_date=args.start_date,
                end_date=args.end_date,
                notebook_id_hash=args.notebook_id_hash,
                event_limit=max(1, args.event_limit),
            )
        }
    else:
        payload = {
            "events": query_notebooklm_activity_events(
                runs_root,
                event=args.event,
                text_query=args.text_query,
                notebook_id_hash=args.notebook_id_hash,
                start_date=args.start_date,
                end_date=args.end_date,
                limit=max(1, args.limit),
            )
        }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
