#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _demo_units():
    from src.reporting.structure_report import TextUnit  # noqa: PLC0415

    return [
        TextUnit("demo-q1", "demo-hearing-1", "transcript_file", "Q: Where were you that evening?"),
        TextUnit("demo-a1", "demo-hearing-1", "transcript_file", "A: At home in Brisbane."),
        TextUnit(
            "demo-j1",
            "demo-journal-1",
            "text_file",
            "Picasso met Alice in Paris and was sad that day because he couldn't have his croissant.",
        ),
        TextUnit("demo-j2", "demo-journal-1", "text_file", "Mary Jane is Bob's sister."),
        TextUnit("demo-j3", "demo-journal-1", "text_file", "Alice is the guardian of Carol."),
        TextUnit("demo-j4", "demo-journal-1", "text_file", "Mary cared for Bob."),
        TextUnit("demo-j5", "demo-journal-1", "text_file", "Alice looks after Carol."),
        TextUnit("demo-chat-1", "demo-chat-1", "transcript_file", "[5/3/26 8:52 pm] Alice: Thanks for following up."),
        TextUnit("demo-chat-2", "demo-chat-2", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
        TextUnit("demo-chat-3", "demo-chat-2", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/report the deterministic transcript/freeform semantic pipeline.")
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--transcript-file", action="append", default=[])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("report")
    sub.add_parser("summary")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    sensiblaw_root = repo_root / "SensibLaw"
    if str(sensiblaw_root) not in sys.path:
        sys.path.insert(0, str(sensiblaw_root))

    from src.gwb_us_law.semantic import ensure_gwb_semantic_schema  # noqa: PLC0415
    from src.reporting.structure_report import load_file_units  # noqa: PLC0415
    from src.transcript_semantic.semantic import (  # noqa: PLC0415
        build_transcript_relation_summary,
        build_transcript_semantic_report,
        run_transcript_semantic_pipeline,
    )

    units = []
    for transcript_path in args.transcript_file:
        units.extend(load_file_units(transcript_path, "transcript_file"))
    if not units:
        units = _demo_units()
    run_id = args.run_id or "transcript-semantic-demo-v1"
    known_participants = {"demo-hearing-1": ["counsel", "witness"]}

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        run_payload = run_transcript_semantic_pipeline(
            conn,
            units,
            known_participants_by_source=known_participants,
            run_id=run_id,
        )
        if args.cmd == "run":
            payload = run_payload
        elif args.cmd == "summary":
            payload = build_transcript_relation_summary(conn, run_id=str(run_payload["run_id"]), units=units)
        else:
            payload = build_transcript_semantic_report(conn, run_id=str(run_payload["run_id"]), units=units)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
