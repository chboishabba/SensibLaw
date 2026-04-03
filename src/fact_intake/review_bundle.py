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


def build_bundle_workflow_summary(
    *,
    review_summary: Mapping[str, Any],
    operator_views: Mapping[str, Any],
    promotion_gate: Mapping[str, Any] | None = None,
    default_fact_id: str | None = None,
) -> dict[str, Any]:
    summary_counts = (
        review_summary.get("summary") if isinstance(review_summary.get("summary"), Mapping) else {}
    )
    chronology_summary = (
        review_summary.get("chronology_summary")
        if isinstance(review_summary.get("chronology_summary"), Mapping)
        else {}
    )
    contested_summary = (
        review_summary.get("contested_summary")
        if isinstance(review_summary.get("contested_summary"), Mapping)
        else {}
    )
    authority_follow = (
        operator_views.get("authority_follow")
        if isinstance(operator_views.get("authority_follow"), Mapping)
        else {}
    )
    authority_follow_summary = (
        authority_follow.get("summary")
        if isinstance(authority_follow.get("summary"), Mapping)
        else {}
    )
    authority_follow_queue = (
        authority_follow.get("queue")
        if isinstance(authority_follow.get("queue"), list)
        else []
    )
    intake_triage = (
        operator_views.get("intake_triage")
        if isinstance(operator_views.get("intake_triage"), Mapping)
        else {}
    )
    intake_groups = (
        intake_triage.get("groups")
        if isinstance(intake_triage.get("groups"), Mapping)
        else {}
    )
    review_filters = [
        str(key)
        for key, rows in intake_groups.items()
        if str(key).strip() and str(key) != "all" and isinstance(rows, list) and rows
    ]

    review_queue_count = int(summary_counts.get("review_queue_count") or 0)
    contested_followup_count = int(contested_summary.get("needs_followup_count") or 0)
    authority_follow_queue_count = int(
        authority_follow_summary.get("queue_count") or len(authority_follow_queue)
    )
    undated_event_count = int(chronology_summary.get("undated_event_count") or 0)
    no_event_fact_count = int(chronology_summary.get("no_event_fact_count") or 0)
    gate_decision = (
        str(promotion_gate.get("decision") or "").strip()
        if isinstance(promotion_gate, Mapping)
        else None
    )

    counts = {
        "review_queue_count": review_queue_count,
        "contested_followup_count": contested_followup_count,
        "authority_follow_queue_count": authority_follow_queue_count,
        "undated_event_count": undated_event_count,
        "no_event_fact_count": no_event_fact_count,
    }

    if authority_follow_queue_count > 0:
        return {
            "stage": "follow_up",
            "title": "Resolve authority follow-up items",
            "recommended_view": "authority_follow",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": f"{authority_follow_queue_count} authority follow-up item(s) remain open.",
            "counts": counts,
            "promotion_gate": dict(promotion_gate or {}),
        }
    if contested_followup_count > 0:
        return {
            "stage": "follow_up",
            "title": "Resolve contested review items",
            "recommended_view": "contested_items",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": f"{contested_followup_count} contested item(s) still need follow-up.",
            "counts": counts,
            "promotion_gate": dict(promotion_gate or {}),
        }
    if review_queue_count > 0:
        gate_note = " The current promotion gate is audit." if gate_decision == "audit" else ""
        return {
            "stage": "decide",
            "title": "Review unresolved facts",
            "recommended_view": "intake_triage",
            "recommended_filter": review_filters[0] if review_filters else "all",
            "focus_fact_id": default_fact_id,
            "reason": f"{review_queue_count} fact(s) remain in the review queue.{gate_note}",
            "counts": counts,
            "promotion_gate": dict(promotion_gate or {}),
        }
    if undated_event_count > 0 or no_event_fact_count > 0:
        return {
            "stage": "inspect",
            "title": "Inspect chronology pressure before handoff",
            "recommended_view": "chronology_prep",
            "recommended_filter": None,
            "focus_fact_id": default_fact_id,
            "reason": (
                f"Chronology still has {undated_event_count} undated event(s) and "
                f"{no_event_fact_count} no-event fact(s)."
            ),
            "counts": counts,
            "promotion_gate": dict(promotion_gate or {}),
        }
    return {
        "stage": "record",
        "title": "Record and hand off the bounded review state",
        "recommended_view": "professional_handoff",
        "recommended_filter": None,
        "focus_fact_id": default_fact_id,
        "reason": "No open follow-up, review-queue, or chronology pressure is blocking the current bundle.",
        "counts": counts,
        "promotion_gate": dict(promotion_gate or {}),
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
    workflow_summary: Mapping[str, Any] | None = None,
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
        "workflow_summary": dict(workflow_summary or {}),
        "abstentions": dict(abstentions),
        "semantic_context": dict(semantic_context),
    }
