#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging

ProgressCallback = Callable[[str, dict[str, Any]], None]


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


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def build_transcript_semantic_cli_payload(
    *,
    db_path: str,
    run_id: str,
    transcript_files: list[str],
    cmd: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
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
    _emit_progress(progress_callback, "load_units_started", source_file_count=len(transcript_files))
    for transcript_path in transcript_files:
        units.extend(load_file_units(transcript_path, "transcript_file"))
        _emit_progress(progress_callback, "source_loaded", path=str(transcript_path), cumulative_unit_count=len(units))
    if not units:
        _emit_progress(progress_callback, "demo_units_used")
        units = _demo_units()
    _emit_progress(progress_callback, "load_units_finished", unit_count=len(units))
    selected_run_id = run_id or "transcript-semantic-demo-v1"
    known_participants = {"demo-hearing-1": ["counsel", "witness"]}

    _emit_progress(progress_callback, "semantic_pipeline_started", db_path=str(db_path), run_id=selected_run_id, unit_count=len(units))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        run_payload = run_transcript_semantic_pipeline(
            conn,
            units,
            known_participants_by_source=known_participants,
            run_id=selected_run_id,
        )
        _emit_progress(
            progress_callback,
            "semantic_pipeline_finished",
            run_id=str(run_payload["run_id"]),
            relation_candidate_count=int(run_payload.get("relation_candidate_count") or 0),
            promoted_relation_count=int(run_payload.get("promoted_relation_count") or 0),
        )
        if cmd == "run":
            payload = run_payload
        elif cmd == "summary":
            _emit_progress(progress_callback, "summary_build_started", run_id=str(run_payload["run_id"]))
            payload = build_transcript_relation_summary(conn, run_id=str(run_payload["run_id"]), units=units)
            _emit_progress(progress_callback, "summary_build_finished", run_id=str(run_payload["run_id"]))
        else:
            _emit_progress(progress_callback, "report_build_started", run_id=str(run_payload["run_id"]))
            payload = build_transcript_semantic_report(conn, run_id=str(run_payload["run_id"]), units=units)
            _emit_progress(progress_callback, "report_build_finished", run_id=str(run_payload["run_id"]))
    _emit_progress(progress_callback, "build_finished", cmd=cmd, run_id=str(payload.get("run_id") or run_payload.get("run_id") or ""))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run/report the deterministic transcript/freeform semantic pipeline.")
    parser.add_argument("--db-path", default=".cache_local/itir.sqlite")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--transcript-file", action="append", default=[])
    parser.add_argument("--progress", action="store_true", help="Emit stage progress JSON to stderr.")
    parser.add_argument(
        "--progress-format",
        choices=("human", "json", "bar"),
        default="human",
        help="Progress renderer for stderr output.",
    )
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("report")
    sub.add_parser("summary")

    args = parser.parse_args()
    configure_cli_logging(args.log_level)
    payload = build_transcript_semantic_cli_payload(
        db_path=args.db_path,
        run_id=args.run_id,
        transcript_files=list(args.transcript_file),
        cmd=args.cmd,
        progress_callback=build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format)),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
