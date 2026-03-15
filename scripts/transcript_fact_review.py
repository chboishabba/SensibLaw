#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import (
    build_fact_intake_payload_from_transcript_report,
    build_transcript_fact_review_bundle,
    persist_fact_intake_payload,
    record_fact_workflow_link,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.structure_report import TextUnit, load_file_units
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


def _demo_units() -> list[TextUnit]:
    return [
        TextUnit("demo-q1", "demo-hearing-1", "transcript_file", "Q: Where were you that evening?"),
        TextUnit("demo-a1", "demo-hearing-1", "transcript_file", "A: At home in Brisbane."),
        TextUnit("demo-chat-1", "demo-chat-1", "transcript_file", "[5/3/26 8:52 pm] Alice: Thanks for following up."),
    ]


def _parse_known_participants(values: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        if "=" not in text:
            raise SystemExit("--known-participants entries must look like source_id=name1,name2")
        source_id, names_csv = text.split("=", 1)
        names = [item.strip() for item in names_csv.split(",") if item.strip()]
        if not source_id.strip() or not names:
            raise SystemExit("--known-participants entries must include a source_id and at least one participant")
        out[source_id.strip()] = names
    return out


def _load_units(paths: list[str], *, use_demo: bool) -> list[TextUnit]:
    units: list[TextUnit] = []
    for transcript_path in paths:
        units.extend(load_file_units(transcript_path, "transcript_file"))
    if units:
        return units
    if use_demo:
        return _demo_units()
    raise SystemExit("Provide at least one --transcript-file or pass --use-demo")


def _build_bundle_payload(
    conn: sqlite3.Connection,
    *,
    units: list[TextUnit],
    run_id: str | None,
    known_participants: dict[str, list[str]],
    source_label: str | None,
    notes: str | None,
) -> dict[str, Any]:
    semantic_run = run_transcript_semantic_pipeline(
        conn,
        units,
        known_participants_by_source=known_participants,
        run_id=run_id or "transcript-fact-review-v1",
    )
    semantic_run_id = str(semantic_run["run_id"])
    semantic_report = build_transcript_semantic_report(conn, run_id=semantic_run_id, units=units)
    fact_payload = build_fact_intake_payload_from_transcript_report(
        semantic_report,
        source_label=source_label,
        notes=notes,
    )
    fact_persist = persist_fact_intake_payload(conn, fact_payload)
    fact_run_id = str(fact_payload["run"]["run_id"])
    workflow_link = record_fact_workflow_link(
        conn,
        workflow_kind="transcript_semantic",
        workflow_run_id=semantic_run_id,
        fact_run_id=fact_run_id,
        source_label=fact_payload["run"].get("source_label"),
    )
    bundle = build_transcript_fact_review_bundle(conn, fact_run_id=fact_run_id, semantic_report=semantic_report)
    return {
        "semantic_run": semantic_run,
        "semantic_report": semantic_report,
        "fact_payload": fact_payload,
        "fact_persist": fact_persist,
        "workflow_link": workflow_link,
        "bundle": bundle,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build transcript-backed fact review bundles over the Mary-parity fact substrate.")
    parser.add_argument("--db-path", type=Path, default=Path(".cache_local/itir.sqlite"))
    parser.add_argument("--run-id", default="", help="Optional transcript semantic run_id")
    parser.add_argument("--transcript-file", action="append", default=[], help="Transcript/chat file to load as transcript_file units")
    parser.add_argument("--known-participants", action="append", default=[], help="Optional source_id=name1,name2 mapping")
    parser.add_argument("--source-label", default=None, help="Optional source label override for the fact-intake run")
    parser.add_argument("--notes", default=None, help="Optional notes for the fact-intake run")
    parser.add_argument("--use-demo", action="store_true", help="Use built-in demo transcript units when no files are provided")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run transcript semantic + fact-intake persistence and print summary identifiers/counts")
    sub.add_parser("bundle", help="Print the full fact.review.bundle.v1 payload")
    sub.add_parser("report", help="Print the full transcript semantic report plus fact persistence summary")

    args = parser.parse_args(argv)
    units = _load_units(args.transcript_file, use_demo=bool(args.use_demo))
    known_participants = _parse_known_participants(args.known_participants)

    with sqlite3.connect(str(args.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        payload = _build_bundle_payload(
            conn,
            units=units,
            run_id=args.run_id.strip() or None,
            known_participants=known_participants,
            source_label=args.source_label,
            notes=args.notes,
        )
    if args.command == "bundle":
        output: dict[str, Any] = payload["bundle"]
    elif args.command == "report":
        output = {
            "semanticRun": payload["semantic_run"],
            "semanticReport": payload["semantic_report"],
            "factPersist": payload["fact_persist"],
            "factRunId": payload["fact_payload"]["run"]["run_id"],
            "bundleSummary": payload["bundle"]["summary"],
            "operatorViews": payload["bundle"].get("operator_views"),
            "workflowLink": payload["workflow_link"],
            "reopenQuery": {
                "workflowKind": "transcript_semantic",
                "workflowRunId": payload["workflow_link"]["workflow_run_id"],
                "factRunId": payload["workflow_link"]["fact_run_id"],
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
            "latestSourceQuery": {
                "workflowKind": "transcript_semantic",
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
        }
    else:
        output = {
            "semanticRun": payload["semantic_run"],
            "factPersist": payload["fact_persist"],
            "semanticRunId": payload["semantic_report"]["run_id"],
            "factRunId": payload["fact_payload"]["run"]["run_id"],
            "workflowLink": payload["workflow_link"],
            "reopenQuery": {
                "workflowKind": "transcript_semantic",
                "workflowRunId": payload["workflow_link"]["workflow_run_id"],
                "factRunId": payload["workflow_link"]["fact_run_id"],
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
            "latestSourceQuery": {
                "workflowKind": "transcript_semantic",
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
            "bundleSummary": payload["bundle"]["summary"],
            "reviewQueueCount": len(payload["bundle"]["review_queue"]),
            "chronologyCount": len(payload["bundle"]["chronology"]),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
