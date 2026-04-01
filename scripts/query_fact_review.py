#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parent
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from src.fact_intake import (
    FEEDBACK_RECEIPT_VERSION,
    build_authority_ingest_summary,
    build_contested_affidavit_proving_slice,
    build_contested_affidavit_review_summary,
    build_feedback_receipt_summary,
    build_fact_agent_feedback_payload,
    build_fact_review_acceptance_report,
    build_fact_review_operator_views,
    build_fact_intake_report,
    build_fact_review_run_summary,
    build_fact_semantic_status_report,
    build_fact_review_workbench_payload,
    find_latest_fact_workflow_link,
    list_fact_intake_runs,
    list_fact_review_sources,
    list_contested_affidavit_review_runs,
    list_authority_ingest_runs,
    list_feedback_receipts,
    list_semantic_refresh_runs,
    persist_feedback_receipt,
    resolve_fact_run_id,
    resolve_fact_run_link,
)
from src.storage.sqlite_runtime import connect_sqlite, resolve_sqlite_db_path

_ACCEPTANCE_WAVE_CHOICES = [
    "wave1_legal",
    "wave2_balanced",
    "wave3_trauma_advocacy",
    "wave3_public_knowledge",
    "wave4_family_law",
    "wave4_medical_regulatory",
    "wave5_handoff_false_coherence",
    "all",
]

_FEEDBACK_CLASS_CHOICES = ["competitor_frustration", "suite_frustration", "delight_signal"]
_FEEDBACK_SOURCE_KIND_CHOICES = ["interview", "usability_session", "chat_thread", "operator_note", "story_proxy"]
_FEEDBACK_SEVERITY_CHOICES = ["low", "medium", "high", "critical"]
_FEEDBACK_SENTIMENT_CHOICES = ["negative", "neutral", "positive"]


def _add_run_selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", default=argparse.SUPPRESS, help="Fact-review run_id to inspect")
    parser.add_argument("--workflow-kind", default=argparse.SUPPRESS, help="Optional workflow kind for reopen lookup")
    parser.add_argument("--workflow-run-id", default=argparse.SUPPRESS, help="Optional source workflow run_id for reopen lookup")
    parser.add_argument("--source-label", default=argparse.SUPPRESS, help="Optional source label filter when resolving latest workflow links")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_json_arg(raw: str | None, *, label: str, default: object | None = None) -> object | None:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} must be valid JSON: {exc}") from exc


def _coerce_feedback_payload(raw: object, *, default_captured_at: str | None = None) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise SystemExit("feedback payload must be a JSON object")
    payload = dict(raw)
    payload.setdefault("schema_version", FEEDBACK_RECEIPT_VERSION)
    if not payload.get("captured_at"):
        payload["captured_at"] = default_captured_at or _utc_now_iso()
    return payload


def _build_feedback_payload_from_args(args: argparse.Namespace) -> dict[str, object]:
    provenance = _parse_json_arg(getattr(args, "provenance_json", None), label="--provenance-json", default={})
    if provenance is None:
        provenance = {}
    if not isinstance(provenance, dict):
        raise SystemExit("--provenance-json must decode to a JSON object")
    if getattr(args, "provenance_collector", None):
        provenance["collector"] = args.provenance_collector
    if getattr(args, "provenance_source_ref", None):
        provenance["source_ref"] = args.provenance_source_ref

    payload: dict[str, object] = {
        "schema_version": FEEDBACK_RECEIPT_VERSION,
        "feedback_class": args.feedback_class,
        "role_label": args.role_label,
        "task_label": args.task_label,
        "source_kind": args.source_kind,
        "summary": args.summary,
        "quote_text": args.quote_text,
        "severity": args.severity,
        "captured_at": getattr(args, "captured_at", None) or _utc_now_iso(),
    }
    for field in ("target_product", "target_surface", "workflow_label", "desired_outcome", "sentiment"):
        value = getattr(args, field, None)
        if value:
            payload[field] = value
    if getattr(args, "tag", None):
        payload["tags"] = list(args.tag)
    if provenance:
        payload["provenance"] = provenance
    return payload


def _load_feedback_import_payloads(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise SystemExit(f"--input {path} does not exist")
    if path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            return [_coerce_feedback_payload(loaded)]
        if isinstance(loaded, list):
            return [_coerce_feedback_payload(item) for item in loaded]
        raise SystemExit("--input JSON must contain an object or list of objects")
    payloads: list[dict[str, object]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--input JSONL line {line_number} is invalid JSON: {exc}") from exc
        payloads.append(_coerce_feedback_payload(loaded))
    return payloads


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

    semantic_p = sub.add_parser("semantic-status", help="Show semantic materialization status and counts for a persisted run")
    _add_run_selector_args(semantic_p)

    refreshes_p = sub.add_parser("semantic-refreshes", help="List recent semantic refresh receipts")
    _add_run_selector_args(refreshes_p)
    refreshes_p.add_argument("--limit", type=int, default=20)

    feedback_p = sub.add_parser("feedback", help="Show downstream agent-facing policy/constraint payload for a persisted run")
    _add_run_selector_args(feedback_p)

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
    acceptance_p.add_argument("--wave", default="all", choices=_ACCEPTANCE_WAVE_CHOICES)
    acceptance_p.add_argument("--fixture-kind", default="unknown", choices=["unknown", "synthetic", "real"])

    demo_p = sub.add_parser("demo-bundle", help="Show a captured Mary demo bundle over a resolved persisted run")
    _add_run_selector_args(demo_p)
    demo_p.add_argument("--wave", default="wave1_legal", choices=_ACCEPTANCE_WAVE_CHOICES)
    demo_p.add_argument("--fixture-kind", default="unknown", choices=["unknown", "synthetic", "real"])

    report_p = sub.add_parser("report", help="Show the full persisted fact-intake report")
    _add_run_selector_args(report_p)

    contested_runs_p = sub.add_parser("contested-runs", help="List persisted contested affidavit review runs")
    contested_runs_p.add_argument("--limit", type=int, default=20)
    contested_runs_p.add_argument("--source-kind", default=None)
    contested_runs_p.add_argument("--source-label", default=None)

    contested_summary_p = sub.add_parser("contested-summary", help="Show one persisted contested affidavit review run")
    contested_summary_p.add_argument("--review-run-id", required=True)

    contested_slice_p = sub.add_parser(
        "contested-proving-slice",
        help="Show the bounded local-first proving-slice read model for one persisted contested affidavit review run",
    )
    contested_slice_p.add_argument("--review-run-id", required=True)

    contested_rows_p = sub.add_parser(
        "contested-rows",
        help="Show a narrow SQLite-first row inspection surface for one persisted contested affidavit review run",
    )
    contested_rows_p.add_argument("--review-run-id", required=True)
    contested_rows_p.add_argument("--proposition-id", action="append", default=[])
    contested_rows_p.add_argument("--limit", type=int, default=20)

    authority_runs_p = sub.add_parser("authority-runs", help="List persisted authority ingest runs")
    authority_runs_p.add_argument("--limit", type=int, default=20)
    authority_runs_p.add_argument("--authority-kind", default=None)

    authority_summary_p = sub.add_parser("authority-summary", help="Show one persisted authority ingest run")
    authority_summary_p.add_argument("--ingest-run-id", required=True)

    feedback_receipts_p = sub.add_parser("feedback-receipts", help="List persisted feedback receipts")
    feedback_receipts_p.add_argument("--limit", type=int, default=20)
    feedback_receipts_p.add_argument("--feedback-class", default=None)
    feedback_receipts_p.add_argument("--source-kind", default=None)
    feedback_receipts_p.add_argument("--target-product", default=None)

    feedback_summary_p = sub.add_parser("feedback-summary", help="Show one persisted feedback receipt")
    feedback_summary_p.add_argument("--receipt-id", required=True)

    feedback_add_p = sub.add_parser("feedback-add", help="Persist one feedback receipt")
    feedback_add_p.add_argument("--feedback-class", required=True, choices=_FEEDBACK_CLASS_CHOICES)
    feedback_add_p.add_argument("--role-label", required=True)
    feedback_add_p.add_argument("--task-label", required=True)
    feedback_add_p.add_argument("--source-kind", required=True, choices=_FEEDBACK_SOURCE_KIND_CHOICES)
    feedback_add_p.add_argument("--summary", required=True)
    feedback_add_p.add_argument("--quote-text", required=True)
    feedback_add_p.add_argument("--severity", required=True, choices=_FEEDBACK_SEVERITY_CHOICES)
    feedback_add_p.add_argument("--captured-at", default=None)
    feedback_add_p.add_argument("--target-product", default=None)
    feedback_add_p.add_argument("--target-surface", default=None)
    feedback_add_p.add_argument("--workflow-label", default=None)
    feedback_add_p.add_argument("--desired-outcome", default=None)
    feedback_add_p.add_argument("--sentiment", default=None, choices=_FEEDBACK_SENTIMENT_CHOICES)
    feedback_add_p.add_argument("--tag", action="append", default=[])
    feedback_add_p.add_argument("--provenance-collector", default=None)
    feedback_add_p.add_argument("--provenance-source-ref", default=None)
    feedback_add_p.add_argument("--provenance-json", default=None)

    feedback_import_p = sub.add_parser("feedback-import", help="Import feedback receipts from local JSONL/JSON")
    feedback_import_p.add_argument("--input", type=Path, required=True)

    args = parser.parse_args(argv)
    db_path = resolve_sqlite_db_path(args.db_path)
    with connect_sqlite(db_path) as conn:
        if args.command == "runs":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
                "sources": list_fact_review_sources(conn, limit=args.limit, workflow_kind=getattr(args, "workflow_kind", None)),
            }
        elif args.command == "resolve-workflow":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
                "run": summary["run"],
                "chronology_summary": summary["chronology_summary"],
                "chronology": summary["chronology"],
                "chronology_groups": summary["chronology_groups"],
            }
        elif args.command == "semantic-status":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "semantic_status": build_fact_semantic_status_report(conn, run_id=resolved_run_id),
            }
        elif args.command == "semantic-refreshes":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            ) if any(getattr(args, name, None) for name in ("run_id", "workflow_kind", "workflow_run_id", "source_label")) else None
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "refreshes": list_semantic_refresh_runs(conn, run_id=resolved_run_id, limit=args.limit),
            }
        elif args.command == "feedback":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "feedback": build_fact_agent_feedback_payload(conn, run_id=resolved_run_id),
            }
        elif args.command == "contested-runs":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "runs": list_contested_affidavit_review_runs(
                    conn,
                    limit=args.limit,
                    source_kind=getattr(args, "source_kind", None),
                    source_label=getattr(args, "source_label", None),
                ),
            }
        elif args.command == "contested-summary":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "review": build_contested_affidavit_review_summary(
                    conn,
                    review_run_id=getattr(args, "review_run_id", None),
                ),
            }
        elif args.command == "contested-proving-slice":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "proving_slice": build_contested_affidavit_proving_slice(
                    conn,
                    review_run_id=getattr(args, "review_run_id", None),
                ),
            }
        elif args.command == "contested-rows":
            review_run_id = str(getattr(args, "review_run_id", None) or "").strip()
            proposition_ids = [str(value).strip() for value in getattr(args, "proposition_id", []) if str(value).strip()]
            sql = """
                SELECT
                  proposition_id,
                  paragraph_id,
                  paragraph_order,
                  sentence_order,
                  proposition_text,
                  coverage_status,
                  best_source_row_id,
                  best_match_score,
                  best_adjusted_match_score,
                  best_match_basis,
                  best_match_excerpt,
                  duplicate_match_excerpt,
                  best_response_role,
                  support_status,
                  semantic_basis,
                  promotion_status,
                  promotion_basis,
                  promotion_reason,
                  support_direction,
                  conflict_state,
                  evidentiary_state,
                  operational_status,
                  relation_root,
                  relation_leaf,
                  primary_target_component,
                  explanation_json,
                  missing_dimensions_json,
                  matched_source_rows_json
                FROM contested_review_affidavit_rows
                WHERE review_run_id = ?
            """
            params: list[object] = [review_run_id]
            if proposition_ids:
                placeholders = ", ".join("?" for _ in proposition_ids)
                sql += f" AND proposition_id IN ({placeholders})"
                params.extend(proposition_ids)
            sql += " ORDER BY paragraph_order, sentence_order, proposition_id LIMIT ?"
            params.append(int(getattr(args, "limit", 20)))
            rows = conn.execute(sql, params).fetchall()
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "review_run_id": review_run_id,
                "rows": [
                    {
                        "proposition_id": str(row["proposition_id"]),
                        "paragraph_id": row["paragraph_id"],
                        "paragraph_order": int(row["paragraph_order"] or 0),
                        "sentence_order": int(row["sentence_order"] or 0),
                        "proposition_text": row["proposition_text"],
                        "coverage_status": row["coverage_status"],
                        "best_source_row_id": row["best_source_row_id"],
                        "best_match_score": row["best_match_score"],
                        "best_adjusted_match_score": row["best_adjusted_match_score"],
                        "best_match_basis": row["best_match_basis"],
                        "best_match_excerpt": row["best_match_excerpt"],
                        "duplicate_match_excerpt": row["duplicate_match_excerpt"],
                        "best_response_role": row["best_response_role"],
                        "support_status": row["support_status"],
                        "semantic_basis": row["semantic_basis"],
                        "promotion_status": row["promotion_status"],
                        "promotion_basis": row["promotion_basis"],
                        "promotion_reason": row["promotion_reason"],
                        "support_direction": row["support_direction"],
                        "conflict_state": row["conflict_state"],
                        "evidentiary_state": row["evidentiary_state"],
                        "operational_status": row["operational_status"],
                        "relation_root": row["relation_root"],
                        "relation_leaf": row["relation_leaf"],
                        "primary_target_component": row["primary_target_component"],
                        "explanation": _parse_json_arg(row["explanation_json"], label="explanation_json", default={}),
                        "missing_dimensions": _parse_json_arg(row["missing_dimensions_json"], label="missing_dimensions_json", default=[]),
                        "matched_source_rows": _parse_json_arg(row["matched_source_rows_json"], label="matched_source_rows_json", default=[]),
                    }
                    for row in rows
                ],
            }
        elif args.command == "authority-runs":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "runs": list_authority_ingest_runs(
                    conn,
                    limit=args.limit,
                    authority_kind=getattr(args, "authority_kind", None),
                ),
            }
        elif args.command == "authority-summary":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "summary": build_authority_ingest_summary(
                    conn,
                    ingest_run_id=getattr(args, "ingest_run_id", None),
                ),
            }
        elif args.command == "feedback-receipts":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "receipts": list_feedback_receipts(
                    conn,
                    limit=args.limit,
                    feedback_class=getattr(args, "feedback_class", None),
                    source_kind=getattr(args, "source_kind", None),
                    target_product=getattr(args, "target_product", None),
                ),
            }
        elif args.command == "feedback-summary":
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "summary": build_feedback_receipt_summary(
                    conn,
                    receipt_id=getattr(args, "receipt_id", None),
                ),
            }
        elif args.command == "feedback-add":
            receipt = persist_feedback_receipt(conn, _build_feedback_payload_from_args(args))
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "receipt": receipt,
            }
        elif args.command == "feedback-import":
            imported_payloads = _load_feedback_import_payloads(args.input)
            receipts = [persist_feedback_receipt(conn, item) for item in imported_payloads]
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "input": str(args.input.resolve()),
                "imported_count": len(receipts),
                "receipts": receipts,
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
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
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
                "dbPath": str(db_path),
                "acceptance": build_fact_review_acceptance_report(
                    workbench,
                    wave=args.wave,
                    fixture_kind=args.fixture_kind,
                ),
            }
        elif args.command == "demo-bundle":
            resolved_run_id = resolve_fact_run_id(
                conn,
                run_id=getattr(args, "run_id", None),
                workflow_kind=getattr(args, "workflow_kind", None),
                workflow_run_id=getattr(args, "workflow_run_id", None),
                source_label=getattr(args, "source_label", None),
            )
            workbench = build_fact_review_workbench_payload(conn, run_id=resolved_run_id)
            resolved_workflow_kind = (
                getattr(args, "workflow_kind", None)
                or workbench.get("reopen_navigation", {}).get("query", {}).get("workflow_kind")
                or workbench.get("reopen_navigation", {}).get("current", {}).get("workflow_kind")
                or workbench.get("run", {}).get("workflow_link", {}).get("workflow_kind")
            )
            resolved_workflow_run_id = (
                getattr(args, "workflow_run_id", None)
                or workbench.get("reopen_navigation", {}).get("query", {}).get("workflow_run_id")
                or workbench.get("reopen_navigation", {}).get("current", {}).get("workflow_run_id")
                or workbench.get("run", {}).get("workflow_link", {}).get("workflow_run_id")
            )
            resolved_source_label = (
                getattr(args, "source_label", None)
                or workbench.get("reopen_navigation", {}).get("query", {}).get("source_label")
                or workbench.get("reopen_navigation", {}).get("current", {}).get("source_label")
                or workbench.get("run", {}).get("source_label")
            )
            payload = {
                "ok": True,
                "dbPath": str(db_path),
                "selector": {
                    "run_id": resolved_run_id,
                    "workflow_kind": resolved_workflow_kind,
                    "workflow_run_id": resolved_workflow_run_id,
                    "source_label": resolved_source_label,
                    "wave": args.wave,
                    "fixture_kind": args.fixture_kind,
                },
                "workbench": workbench,
                "acceptance": build_fact_review_acceptance_report(
                    workbench,
                    wave=args.wave,
                    fixture_kind=args.fixture_kind,
                ),
                "sources": list_fact_review_sources(
                    conn,
                    workflow_kind=resolved_workflow_kind,
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
                "dbPath": str(db_path),
                "report": build_fact_intake_report(conn, run_id=resolved_run_id),
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
