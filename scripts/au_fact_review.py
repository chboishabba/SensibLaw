#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import sys
from typing import Any, Callable

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from cli_runtime import build_progress_callback, configure_cli_logging
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline
from src.fact_intake import (
    build_au_fact_review_bundle,
    build_fact_intake_payload_from_au_semantic_report,
    persist_fact_intake_payload,
    record_fact_workflow_link,
)
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[str, dict[str, Any]], None]


def _emit_progress(progress_callback: ProgressCallback | None, stage: str, **details: Any) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, details)


def _wrap_fact_persist_progress(progress_callback: ProgressCallback | None) -> Callable[[dict[str, Any]], None] | None:
    if progress_callback is None:
        return None

    def emit(update: dict[str, Any]) -> None:
        stage = str(update.get("stage") or "progress")
        progress_callback(f"fact_persist_{stage}", update)

    return emit


def _build_bundle_payload(
    conn: sqlite3.Connection,
    *,
    timeline_suffix: str,
    run_id: str | None,
    seed_path: Path | None,
    source_label: str | None,
    notes: str | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    if seed_path is not None:
        _emit_progress(progress_callback, "seed_import_started", path=str(seed_path))
        import_au_semantic_seed_payload(conn, json.loads(seed_path.read_text(encoding="utf-8")))
        _emit_progress(progress_callback, "seed_import_finished", path=str(seed_path))
    _emit_progress(progress_callback, "semantic_pipeline_started", timeline_suffix=timeline_suffix)
    semantic_run = run_au_semantic_pipeline(
        conn,
        timeline_suffix=timeline_suffix,
        run_id=run_id or None,
    )
    semantic_run_id = str(semantic_run["run_id"])
    _emit_progress(progress_callback, "semantic_pipeline_finished", semantic_run_id=semantic_run_id)
    _emit_progress(progress_callback, "timeline_load_started", semantic_run_id=semantic_run_id)
    source_payload = load_run_payload_from_normalized(conn, semantic_run_id) or {}
    source_events = source_payload.get("events") if isinstance(source_payload.get("events"), list) else []
    _emit_progress(progress_callback, "timeline_load_finished", source_event_count=len(source_events))
    _emit_progress(progress_callback, "semantic_report_started", semantic_run_id=semantic_run_id)
    semantic_report = build_au_semantic_report(conn, run_id=semantic_run_id)
    _emit_progress(progress_callback, "semantic_report_finished", semantic_run_id=semantic_run_id)
    _emit_progress(progress_callback, "fact_payload_started", semantic_run_id=semantic_run_id)
    fact_payload = build_fact_intake_payload_from_au_semantic_report(
        semantic_report,
        timeline_events=source_events,
        source_label=source_label,
        notes=notes,
    )
    _emit_progress(progress_callback, "fact_payload_finished", fact_run_id=str(fact_payload["run"]["run_id"]))
    LOGGER.info("Persisting AU fact-intake payload for %s", fact_payload["run"]["run_id"])
    fact_persist = persist_fact_intake_payload(
        conn,
        fact_payload,
        progress_callback=_wrap_fact_persist_progress(progress_callback),
    )
    fact_run_id = str(fact_payload["run"]["run_id"])
    workflow_link = record_fact_workflow_link(
        conn,
        workflow_kind="au_semantic",
        workflow_run_id=semantic_run_id,
        fact_run_id=fact_run_id,
        source_label=fact_payload["run"].get("source_label"),
    )
    _emit_progress(progress_callback, "bundle_build_started", fact_run_id=fact_run_id)
    bundle = build_au_fact_review_bundle(
        conn,
        fact_run_id=fact_run_id,
        semantic_report=semantic_report,
        source_events=source_events,
    )
    _emit_progress(progress_callback, "bundle_build_finished", fact_run_id=fact_run_id, review_queue_count=len(bundle.get("review_queue", [])))
    return {
        "semantic_run": semantic_run,
        "semantic_report": semantic_report,
        "fact_payload": fact_payload,
        "fact_persist": fact_persist,
        "workflow_link": workflow_link,
        "bundle": bundle,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build AU-semantic-backed fact review bundles over the Mary-parity fact substrate.")
    parser.add_argument("--db-path", type=Path, default=Path(".cache_local/itir.sqlite"))
    parser.add_argument("--timeline-suffix", default="wiki_timeline_hca_s942025_aoo.json")
    parser.add_argument("--run-id", default="", help="Optional AU semantic run_id override")
    parser.add_argument("--seed-path", type=Path, default=None, help="Optional AU linkage seed payload to import first")
    parser.add_argument("--source-label", default=None, help="Optional source label override for the fact-intake run")
    parser.add_argument("--notes", default=None, help="Optional notes for the fact-intake run")
    parser.add_argument("--progress", action="store_true", help="Emit progress to stderr.")
    parser.add_argument("--progress-format", choices=("human", "json"), default="human", help="Progress renderer for stderr output.")
    parser.add_argument("--log-level", default="INFO", help="stderr logging level (default: %(default)s).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run AU semantic + fact-intake persistence and print summary identifiers/counts")
    sub.add_parser("bundle", help="Print the full fact.review.bundle.v1 payload")
    sub.add_parser("report", help="Print the AU semantic report plus fact persistence summary")

    args = parser.parse_args(argv)
    configure_cli_logging(args.log_level)
    progress_callback = build_progress_callback(enabled=bool(args.progress), fmt=str(args.progress_format))
    with sqlite3.connect(str(args.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        payload = _build_bundle_payload(
            conn,
            timeline_suffix=args.timeline_suffix,
            run_id=args.run_id.strip() or None,
            seed_path=args.seed_path,
            source_label=args.source_label,
            notes=args.notes,
            progress_callback=progress_callback,
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
                "workflowKind": "au_semantic",
                "workflowRunId": payload["workflow_link"]["workflow_run_id"],
                "factRunId": payload["workflow_link"]["fact_run_id"],
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
            "latestSourceQuery": {
                "workflowKind": "au_semantic",
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
                "workflowKind": "au_semantic",
                "workflowRunId": payload["workflow_link"]["workflow_run_id"],
                "factRunId": payload["workflow_link"]["fact_run_id"],
                "sourceLabel": payload["workflow_link"]["source_label"],
            },
            "latestSourceQuery": {
                "workflowKind": "au_semantic",
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
