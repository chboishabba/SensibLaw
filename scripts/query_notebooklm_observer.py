#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.reporting.notebooklm_observer import (  # noqa: E402
    build_notebooklm_observer_report,
    list_notebooklm_observer_dates,
    query_notebooklm_observer_events,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query NotebookLM observer metadata from SB runs.")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("StatiBaker/runs"),
        help="Path to SB runs root containing logs/notes/<date>.jsonl",
    )
    parser.add_argument("--start-date", default=None, help="Optional YYYY-MM-DD lower bound")
    parser.add_argument("--end-date", default=None, help="Optional YYYY-MM-DD upper bound")
    parser.add_argument("--notebook-id-hash", default=None, help="Optional hashed notebook scope")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("dates", help="List NotebookLM observer date coverage")

    summary_parser = subparsers.add_parser("summary", help="Build NotebookLM observer summary")
    summary_parser.add_argument("--event-limit", type=int, default=50, help="Recent event tail size")

    events_parser = subparsers.add_parser("events", help="Query recent NotebookLM observer events")
    events_parser.add_argument("--event", default=None, help="Optional event kind filter")
    events_parser.add_argument("--text-query", default=None, help="Optional case-insensitive title/summary/keyword filter")
    events_parser.add_argument("--limit", type=int, default=25, help="Max rows to return")

    args = parser.parse_args(argv)

    if args.command == "dates":
        payload = {
            "ok": True,
            "runsRoot": str(args.runs_root.expanduser().resolve()),
            "dates": list_notebooklm_observer_dates(
                args.runs_root,
                start_date=args.start_date,
                end_date=args.end_date,
            ),
        }
    elif args.command == "summary":
        payload = {
            "ok": True,
            "report": build_notebooklm_observer_report(
                args.runs_root,
                start_date=args.start_date,
                end_date=args.end_date,
                notebook_id_hash=args.notebook_id_hash,
                event_limit=args.event_limit,
            ),
        }
    else:
        payload = {
            "ok": True,
            "runsRoot": str(args.runs_root.expanduser().resolve()),
            "events": query_notebooklm_observer_events(
                args.runs_root,
                start_date=args.start_date,
                end_date=args.end_date,
                notebook_id_hash=args.notebook_id_hash,
                event=args.event,
                text_query=args.text_query,
                limit=args.limit,
            ),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
