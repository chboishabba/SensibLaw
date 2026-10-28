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
    DEFAULT_QUERY_ROWS,
    MAX_QUERY_ROWS,
    build_bounded_notebooklm_observer_report,
    query_notebooklm_observer_artifacts,
    query_notebooklm_observer_dates,
    query_notebooklm_observer_events,
    query_notebooklm_observer_notebooks,
    query_notebooklm_observer_sources,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Query NotebookLM observer metadata from SB runs."
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("StatiBaker/runs"),
        help="Path to SB runs root containing logs/notes/<date>.jsonl",
    )
    parser.add_argument(
        "--start-date", default=None, help="Optional YYYY-MM-DD lower bound"
    )
    parser.add_argument(
        "--end-date", default=None, help="Optional YYYY-MM-DD upper bound"
    )
    parser.add_argument(
        "--notebook-id-hash", default=None, help="Optional hashed notebook scope"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dates_parser = subparsers.add_parser(
        "dates", help="List bounded NotebookLM observer date coverage"
    )
    dates_parser.add_argument(
        "--limit", type=int, default=DEFAULT_QUERY_ROWS, help="Max date rows to return"
    )

    summary_parser = subparsers.add_parser(
        "summary", help="Build NotebookLM observer summary"
    )
    summary_parser.add_argument(
        "--event-limit",
        type=int,
        default=DEFAULT_QUERY_ROWS,
        help=f"Recent event tail size (hard-capped at {MAX_QUERY_ROWS})",
    )
    summary_parser.add_argument(
        "--entity-limit",
        type=int,
        default=DEFAULT_QUERY_ROWS,
        help=f"Max date/notebook/source/artifact rows per collection (hard-capped at {MAX_QUERY_ROWS})",
    )

    notebooks_parser = subparsers.add_parser(
        "notebooks", help="Query bounded NotebookLM notebook summaries"
    )
    notebooks_parser.add_argument("--text-query", default=None)
    notebooks_parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_ROWS)

    sources_parser = subparsers.add_parser(
        "sources", help="Query bounded NotebookLM source summaries"
    )
    sources_parser.add_argument("--source-type", default=None)
    sources_parser.add_argument("--source-status", default=None)
    sources_parser.add_argument("--text-query", default=None)
    sources_parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_ROWS)

    artifacts_parser = subparsers.add_parser(
        "artifacts", help="Query bounded NotebookLM artifact summaries"
    )
    artifacts_parser.add_argument("--artifact-type", default=None)
    artifacts_parser.add_argument("--artifact-status", default=None)
    artifacts_parser.add_argument("--text-query", default=None)
    artifacts_parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_ROWS)

    events_parser = subparsers.add_parser(
        "events", help="Query recent NotebookLM observer events"
    )
    events_parser.add_argument(
        "--event", default=None, help="Optional event kind filter"
    )
    events_parser.add_argument(
        "--text-query",
        default=None,
        help="Optional case-insensitive title/summary/keyword filter",
    )
    events_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_QUERY_ROWS,
        help=f"Max rows to return (hard-capped at {MAX_QUERY_ROWS})",
    )

    args = parser.parse_args(argv)

    common = {
        "start_date": args.start_date,
        "end_date": args.end_date,
    }
    runs_root = str(args.runs_root.expanduser().resolve())

    if args.command == "dates":
        payload = {
            "ok": True,
            "runsRoot": runs_root,
            "dates": query_notebooklm_observer_dates(
                args.runs_root,
                **common,
                limit=args.limit,
            ),
        }
    elif args.command == "summary":
        payload = {
            "ok": True,
            "report": build_bounded_notebooklm_observer_report(
                args.runs_root,
                **common,
                notebook_id_hash=args.notebook_id_hash,
                event_limit=args.event_limit,
                entity_limit=args.entity_limit,
            ),
        }
    elif args.command == "notebooks":
        payload = {
            "ok": True,
            "runsRoot": runs_root,
            "notebooks": query_notebooklm_observer_notebooks(
                args.runs_root,
                **common,
                notebook_id_hash=args.notebook_id_hash,
                text_query=args.text_query,
                limit=args.limit,
            ),
        }
    elif args.command == "sources":
        payload = {
            "ok": True,
            "runsRoot": runs_root,
            "sources": query_notebooklm_observer_sources(
                args.runs_root,
                **common,
                notebook_id_hash=args.notebook_id_hash,
                source_type=args.source_type,
                source_status=args.source_status,
                text_query=args.text_query,
                limit=args.limit,
            ),
        }
    elif args.command == "artifacts":
        payload = {
            "ok": True,
            "runsRoot": runs_root,
            "artifacts": query_notebooklm_observer_artifacts(
                args.runs_root,
                **common,
                notebook_id_hash=args.notebook_id_hash,
                artifact_type=args.artifact_type,
                artifact_status=args.artifact_status,
                text_query=args.text_query,
                limit=args.limit,
            ),
        }
    else:
        payload = {
            "ok": True,
            "runsRoot": runs_root,
            "events": query_notebooklm_observer_events(
                args.runs_root,
                **common,
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
