from __future__ import annotations

from typing import Any, Mapping

FACT_REVIEW_BUNDLE_VERSION = "fact.review.bundle.v1"


def normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_event_chronology(
    events: list[Mapping[str, Any]],
    *,
    semantic_order: Mapping[str, int],
) -> list[dict[str, Any]]:
    chronology: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        event_id = str(event.get("event_id") or "")
        source_event_ids = [
            str(value)
            for value in event.get("source_event_ids", [])
            if isinstance(value, str) and str(value).strip()
        ]
        semantic_positions = [
            semantic_order[source_event_id]
            for source_event_id in source_event_ids
            if source_event_id in semantic_order
        ]
        chronology.append(
            {
                "order": min(semantic_positions) if semantic_positions else index,
                "event_id": event_id,
                "source_event_ids": source_event_ids,
                "event_type": str(event.get("event_type") or ""),
                "primary_actor": normalize_opt_text(event.get("primary_actor")),
                "object_text": normalize_opt_text(event.get("object_text")),
                "time_start": normalize_opt_text(event.get("time_start")),
                "status": str(event.get("status") or ""),
            }
        )
    chronology.sort(
        key=lambda row: (
            row["time_start"] is None,
            row["time_start"] or "",
            row["order"],
            row["event_id"],
        )
    )
    return chronology


def build_abstentions(fact_report: Mapping[str, Any]) -> dict[str, Any]:
    statements = [
        row for row in fact_report.get("statements", []) if isinstance(row, Mapping)
    ]
    observations = [
        row for row in fact_report.get("observations", []) if isinstance(row, Mapping)
    ]
    facts = [row for row in fact_report.get("facts", []) if isinstance(row, Mapping)]
    return {
        "statement_ids": [
            str(row.get("statement_id") or "")
            for row in statements
            if str(row.get("statement_status") or "") == "abstained"
        ],
        "observation_ids": [
            str(row.get("observation_id") or "")
            for row in observations
            if str(row.get("observation_status") or "") == "abstained"
        ],
        "fact_ids": [
            str(row.get("fact_id") or "")
            for row in facts
            if str(row.get("candidate_status") or "") == "abstained"
        ],
        "counts": {
            "statement_abstentions": sum(
                1
                for row in statements
                if str(row.get("statement_status") or "") == "abstained"
            ),
            "observation_abstentions": sum(
                1
                for row in observations
                if str(row.get("observation_status") or "") == "abstained"
            ),
            "fact_abstentions": sum(
                1
                for row in facts
                if str(row.get("candidate_status") or "") == "abstained"
            ),
        },
    }


def build_fact_review_bundle_payload(
    *,
    fact_report: Mapping[str, Any],
    review_summary: Mapping[str, Any],
    semantic_run_id: str,
    source_documents: list[Mapping[str, Any]],
    chronology: list[dict[str, Any]],
    abstentions: Mapping[str, Any],
    operator_views: Mapping[str, Any],
    semantic_context: Mapping[str, Any],
    chronology_summary_extras: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    chronology_summary = {
        **dict(review_summary.get("chronology_summary", {})),
        "bundle_event_count": len(chronology),
        "bundle_dated_event_count": sum(1 for row in chronology if row["time_start"]),
    }
    if chronology_summary_extras:
        chronology_summary.update(dict(chronology_summary_extras))
    return {
        "version": FACT_REVIEW_BUNDLE_VERSION,
        "run": {
            "fact_run_id": str(fact_report["run"]["run_id"]),
            "semantic_run_id": semantic_run_id,
            "source_label": str(fact_report["run"]["source_label"]),
            "created_at": str(fact_report["run"]["created_at"]),
            "workflow_link": fact_report["run"].get("workflow_link"),
        },
        "summary": {
            **dict(fact_report.get("summary", {})),
            "source_document_count": len(source_documents),
        },
        "source_documents": list(source_documents),
        "sources": list(fact_report.get("sources", [])),
        "excerpts": list(fact_report.get("excerpts", [])),
        "statements": list(fact_report.get("statements", [])),
        "observations": list(fact_report.get("observations", [])),
        "events": list(fact_report.get("events", [])),
        "facts": list(fact_report.get("facts", [])),
        "chronology": chronology,
        "chronology_groups": dict(review_summary.get("chronology_groups", {})),
        "review_queue": list(review_summary.get("review_queue", [])),
        "operator_views": dict(operator_views),
        "contested_summary": dict(review_summary.get("contested_summary", {})),
        "chronology_summary": chronology_summary,
        "abstentions": dict(abstentions),
        "semantic_context": dict(semantic_context),
    }
