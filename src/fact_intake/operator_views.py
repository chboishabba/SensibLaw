"""Operator-control plane view builders for fact-intake workbenches."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .control_plane import build_follow_queue_item


def _normalize_opt_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _join_parts(parts: Iterable[str | None]) -> str | None:
    values = [str(value).strip() for value in parts if str(value or "").strip()]
    return " · ".join(values) if values else None


def _build_review_queue_operator_readout(row: Mapping[str, Any], *, title: str) -> dict[str, Any]:
    status_explanation = row.get("status_explanation") if isinstance(row.get("status_explanation"), Mapping) else {}
    status_line = _join_parts(
        [
            _normalize_opt_text(status_explanation.get("status_value")),
            _normalize_opt_text(status_explanation.get("status_bucket")),
        ]
    )
    return {
        "headline": title,
        "status_line": status_line,
        "reason_line": _normalize_opt_text(status_explanation.get("why"))
        or _normalize_opt_text(row.get("primary_contested_reason_text")),
        "next_action_line": _normalize_opt_text(status_explanation.get("next_action")) or "inspect_row",
    }


def _build_contested_operator_readout(row: Mapping[str, Any], *, title: str) -> dict[str, Any]:
    reason_texts = [str(value) for value in row.get("reason_texts", []) if str(value).strip()]
    contestation_statuses = [str(value) for value in row.get("contestation_statuses", []) if str(value).strip()]
    review_statuses = [str(value) for value in row.get("review_statuses", []) if str(value).strip()]
    status_line = _join_parts(
        [
            ",".join(contestation_statuses) if contestation_statuses else None,
            "needs_followup" if "needs_followup" in review_statuses else ("reviewed" if review_statuses else "open"),
        ]
    )
    next_action = "review_contestation"
    if "needs_followup" in review_statuses:
        next_action = "follow_up_contestation"
    elif bool(row.get("chronology_impacted")):
        next_action = "review_chronology"
    return {
        "headline": title,
        "status_line": status_line,
        "reason_line": " | ".join(reason_texts) if reason_texts else None,
        "next_action_line": next_action,
    }


def review_queue_route_target(row: Mapping[str, Any]) -> str:
    reason_codes = {str(value) for value in row.get("reason_codes", []) if str(value).strip()}
    if "contradictory_chronology" in reason_codes or bool(row.get("chronology_impacted")):
        return "chronology_review"
    if "missing_actor" in reason_codes:
        return "actor_review"
    if "procedural_significance" in reason_codes or bool(row.get("has_legal_procedural_observations")):
        return "procedural_review"
    return "manual_review"


def review_queue_resolution_status(row: Mapping[str, Any]) -> str:
    status = str(row.get("latest_review_status") or "").strip()
    if status:
        return status
    if str(row.get("candidate_status") or "").strip() == "abstained":
        return "abstained"
    return "open"


def build_review_queue_control_items(review_queue: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in review_queue:
        status_explanation = row.get("status_explanation") if isinstance(row.get("status_explanation"), Mapping) else {}
        reason_labels = [str(value) for value in status_explanation.get("reason_labels", []) if str(value).strip()]
        next_action = _normalize_opt_text(status_explanation.get("next_action"))
        title = str(row.get("label") or row.get("fact_id") or "Review item")
        operator_readout = _build_review_queue_operator_readout(row, title=title)
        item = build_follow_queue_item(
            item_id=str(row.get("fact_id") or ""),
            title=title,
            subtitle="review_queue_item",
            description=_normalize_opt_text(status_explanation.get("why")) or _normalize_opt_text(row.get("primary_contested_reason_text")),
            conjecture_kind="review_queue_item",
            route_target=review_queue_route_target(row),
            resolution_status=review_queue_resolution_status(row),
            chips=reason_labels or [str(value) for value in row.get("reason_labels", []) if str(value).strip()],
            detail_rows=[
                {"label": "Status", "value": " · ".join(value for value in [str(status_explanation.get("status_value") or "").strip(), str(status_explanation.get("status_bucket") or "").strip()] if value)},
                {"label": "Next action", "value": next_action or "inspect_row"},
                {"label": "Observation signals", "value": " · ".join(str(value) for value in row.get("signal_classes", []) if str(value).strip())},
                {"label": "Source provenance", "value": " · ".join(str(value) for value in row.get("source_signal_classes", []) if str(value).strip())},
                {"label": "Operator constraints", "value": " · ".join(str(value) for value in row.get("policy_outcomes", []) if str(value).strip())},
            ],
            extra={**dict(row), "operator_readout": operator_readout},
        )
        item["operator_readout"] = operator_readout
        queue.append(item)
    return queue


def contested_item_route_target(row: Mapping[str, Any]) -> str:
    return "chronology_review" if bool(row.get("chronology_impacted")) else "contested_review"


def contested_item_resolution_status(row: Mapping[str, Any]) -> str:
    statuses = {str(value) for value in row.get("review_statuses", []) if str(value).strip()}
    if "needs_followup" in statuses:
        return "needs_followup"
    if statuses:
        return "reviewed"
    return "open"


def build_contested_control_items(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in items:
        reason_texts = [str(value) for value in row.get("reason_texts", []) if str(value).strip()]
        contestation_statuses = [str(value) for value in row.get("contestation_statuses", []) if str(value).strip()]
        review_statuses = [str(value) for value in row.get("review_statuses", []) if str(value).strip()]
        title = str(row.get("label") or row.get("fact_id") or "Contested item")
        operator_readout = _build_contested_operator_readout(row, title=title)
        item = build_follow_queue_item(
            item_id=str(row.get("fact_id") or ""),
            title=title,
            subtitle="contested_fact_item",
            description=" | ".join(reason_texts) if reason_texts else None,
            conjecture_kind="contested_fact_item",
            route_target=contested_item_route_target(row),
            resolution_status=contested_item_resolution_status(row),
            chips=contestation_statuses,
            detail_rows=[
                {"label": "Review statuses", "value": ", ".join(review_statuses)},
                {"label": "Chronology", "value": "impacted" if bool(row.get("chronology_impacted")) else "not impacted"},
            ],
            extra={**dict(row), "operator_readout": operator_readout},
        )
        item["operator_readout"] = operator_readout
        queue.append(item)
    return queue
