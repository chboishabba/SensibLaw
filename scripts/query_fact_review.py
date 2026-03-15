#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import (
    build_fact_review_acceptance_report,
    build_fact_review_operator_views,
    build_fact_intake_report,
    build_fact_review_run_summary,
    build_fact_review_workbench_payload,
    find_latest_fact_workflow_link,
    list_fact_intake_runs,
    list_fact_review_sources,
    resolve_fact_run_id,
    resolve_fact_run_link,
)


def _add_run_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", default=argparse.SUPPRESS, help="Fact-review run_id to inspect")
    parser.add_argument("--workflow-kind", default=argparse.SUPPRESS, help="Optional workflow kind for reopen lookup")
    parser.add_argument("--workflow-run-id", default=argparse.SUPPRESS, help="Optional source workflow run_id for reopen lookup")
    parser.add_argument("--source-label", default=argparse.SUPPRESS, help="Optional source label filter when resolving latest workflow links")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query persisted fact-review runs from the Mary-parity fact substrate.")
    parser.add_argument("--db-path", type=Path, default=Path(".cache_local/itir.sqlite"))
    _add_run_selector_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    runs_p = sub.add_parser("runs", help="List recent fact-review runs")
    runs_p.add_argument("--limit", type=int, default=20)
    runs_p.add_argument("--source-label", default=None)
    runs_p.add_argument("--workflow-kind", default=None)

    sources_p = sub.add_parser("sources", help="List recent source labels with linked fact-review runs")
    sources_p.add_argument("--limit", type=int, default=20)
    sources_p.add_argument("--workflow-kind", default=None)

    resolve_p = sub.add_parser("resolve-workflow", help="Resolve a source workflow run into its persisted fact-review run")
    resolve_p.add_argument("--workflow-kind", required=True)
    resolve_p.add_argument("--workflow-run-id", default=None)
    resolve_p.add_argument("--source-label", default=None)

    latest_p = sub.add_parser("latest-workflow", help="Show the latest persisted fact-review run for a workflow kind")
    latest_p.add_argument("--workflow-kind", required=True)
    latest_p.add_argument("--source-label", default=None)

    summary_p = sub.add_parser("summary", help="Show a compact run summary with review queue and chronology stats")
    _add_run_selector_args(summary_p)

    review_p = sub.add_parser("review-queue", help="Show the review queue for a persisted fact-review run")
    _add_run_selector_args(review_p)

    chronology_p = sub.add_parser("chronology", help="Show chronology-focused event/fact reporting for a persisted run")
    _add_run_selector_args(chronology_p)

    view_p = sub.add_parser("view", help="Show one bounded operator view for a persisted run")
    _add_run_selector_args(view_p)
    view_p.add_argument(
        "--view-kind",
        required=True,
        choices=["intake_triage", "chronology_prep", "procedural_posture", "contested_items"],
    )

    workbench_p = sub.add_parser("workbench", help="Show the bounded read-only fact-review workbench payload")
    _add_run_selector_args(workbench_p)

    acceptance_p = sub.add_parser("acceptance", help="Show story-driven acceptance results for a persisted run")
    _add_run_selector_args(acceptance_p)
    acceptance_p.add_argument("--wave", default="all", choices=["wave1_legal", "wave2_balanced", "wave3_trauma_advocacy", "all"])
    acceptance_p.add_argument("--fixture-kind", default="unknown", choices=["unknown", "synthetic", "real"])

    report_p = sub.add_parser("report", help="Show the full persisted fact-intake report")
    _add_run_selector_args(report_p)

    args = parser.parse_args(argv)
    with sqlite3.connect(str(args.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if args.command == "runs":
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "runs": list_fact_intake_runs(
                    conn,
                    limit=args.limit,
                    source_label=args.source_label,
                    workflow_kind=getattr(args, "workflow_kind", None),
                ),
            }
        elif args.command == "sources":
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "sources": list_fact_review_sources(conn, limit=args.limit, workflow_kind=getattr(args, "workflow_kind", None)),
            }
        elif args.command == "resolve-workflow":
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "workflow_link": resolve_fact_run_link(
                    conn,
                    workflow_kind=getattr(args, "workflow_kind", None),
                    workflow_run_id=getattr(args, "workflow_run_id", None),
                ) if getattr(args, "workflow_run_id", None)
                else find_latest_fact_workflow_link(
                    conn,
                    workflow_kind=getattr(args, "workflow_kind", None),
                    source_label=getattr(args, "source_label", None),
                ),
            }
        elif args.command == "latest-workflow":
            workflow_link = find_latest_fact_workflow_link(
                conn,
                workflow_kind=getattr(args, "workflow_kind", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "workflow_link": workflow_link,
                "summary": build_fact_review_run_summary(conn, run_id=workflow_link["fact_run_id"]),
            }
        elif args.command == "summary":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "summary": build_fact_review_run_summary(conn, run_id=resolved_run_id),
            }
        elif args.command == "review-queue":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            summary = build_fact_review_run_summary(conn, run_id=resolved_run_id)
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "run": summary["run"],
                "summary": summary["summary"],
                "review_queue": summary["review_queue"],
                "contested_summary": summary["contested_summary"],
            }
        elif args.command == "chronology":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            summary = build_fact_review_run_summary(conn, run_id=resolved_run_id)
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "run": summary["run"],
                "chronology_summary": summary["chronology_summary"],
                "chronology": summary["chronology"],
                "chronology_groups": summary["chronology_groups"],
            }
        elif args.command == "view":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            operator_views = build_fact_review_operator_views(conn, run_id=resolved_run_id)
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "run": build_fact_review_run_summary(conn, run_id=resolved_run_id)["run"],
                "view_kind": args.view_kind,
                "view": operator_views[args.view_kind],
            }
        elif args.command == "workbench":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "workbench": build_fact_review_workbench_payload(conn, run_id=resolved_run_id),
            }
        elif args.command == "acceptance":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            workbench = build_fact_review_workbench_payload(conn, run_id=resolved_run_id)
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "acceptance": build_fact_review_acceptance_report(
                    workbench,
                    wave=args.wave,
                    fixture_kind=args.fixture_kind,
                ),
            }
        else:
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(args.db_path.resolve()),
                "report": build_fact_intake_report(conn, run_id=resolved_run_id),
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
