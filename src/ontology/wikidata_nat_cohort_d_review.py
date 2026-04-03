from __future__ import annotations

from typing import Any, Mapping, Sequence


WIKIDATA_NAT_COHORT_D_TYPE_PROBING_SURFACE_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_d_type_probing_surface.v0_1"
)
WIKIDATA_NAT_COHORT_D_OPERATOR_REVIEW_SURFACE_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_d_operator_review_surface.v0_1"
)
WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_d_operator_report.v0_1"
)
WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_BATCH_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_d_operator_report_batch.v0_1"
)
WIKIDATA_NAT_COHORT_D_REVIEW_CONTROL_INDEX_SCHEMA_VERSION = (
    "sl.wikidata_nat_cohort_d_review_control_index.v0_1"
)

MISSING_INSTANCE_OF_TYPING_FLAG = "missing_instance_of_typing_deficit"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [_stringify(item).strip() for item in value if _stringify(item).strip()]


def _smallest_typing_check(packet: Mapping[str, Any]) -> str:
    reviewer_view = packet.get("reviewer_view")
    if not isinstance(reviewer_view, Mapping):
        return "confirm_absence_of_instance_of"
    decision_focus = _string_list(reviewer_view.get("decision_focus"))
    if "resolve_page_open_questions" in decision_focus:
        return "resolve_page_open_questions"
    if decision_focus:
        return decision_focus[0]
    return "confirm_absence_of_instance_of"


def _typing_signal_id(row: Mapping[str, Any]) -> str:
    if not isinstance(row, Mapping):
        return "wikidata:typing-deficit"
    packet_id = _stringify(row.get("packet_id"))
    qid = _stringify(row.get("review_entity_qid"))
    if packet_id:
        return packet_id
    if qid:
        return f"wikidata:{qid}"
    return "wikidata:typing-deficit"


def _build_probe_typing_signal(row: Mapping[str, Any]) -> dict[str, Any]:
    qid = _stringify(row.get("review_entity_qid"))
    return {
        "signal_id": _typing_signal_id(row),
        "source": "wikidata",
        "signal_kind": MISSING_INSTANCE_OF_TYPING_FLAG,
        "linked_qid": qid or None,
        "requested_step": _stringify(row.get("recommended_next_step")),
        "packet_id": _stringify(row.get("packet_id")),
        "details": _stringify(row.get("split_plan_id")),
    }


def build_wikidata_nat_cohort_d_type_probing_surface(
    *,
    cohort_d_review_surface: Mapping[str, Any],
    packet_payloads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    governance = cohort_d_review_surface.get("governance")
    review_surface = cohort_d_review_surface.get("review_surface")
    packet_refs = cohort_d_review_surface.get("candidate_packet_refs")
    if not isinstance(governance, Mapping):
        raise ValueError("cohort_d_review_surface requires governance")
    if not isinstance(review_surface, Mapping):
        raise ValueError("cohort_d_review_surface requires review_surface")
    if not isinstance(packet_refs, list):
        raise ValueError("cohort_d_review_surface requires candidate_packet_refs")

    packet_by_qid: dict[str, Mapping[str, Any]] = {}
    for packet in packet_payloads:
        if not isinstance(packet, Mapping):
            continue
        qid = _stringify(packet.get("review_entity_qid", "")).strip()
        if qid:
            packet_by_qid[qid] = packet

    probe_rows: list[dict[str, Any]] = []
    unresolved_packet_refs: list[dict[str, str]] = []
    for slot in packet_refs:
        if not isinstance(slot, Mapping):
            continue
        qid = _stringify(slot.get("review_entity_qid", "")).strip()
        if not qid:
            continue
        packet = packet_by_qid.get(qid)
        if packet is None:
            unresolved_packet_refs.append(
                {
                    "review_entity_qid": qid,
                    "reason": "missing_packet_payload",
                }
            )
            continue
        split_context = packet.get("split_review_context")
        reviewer_view = packet.get("reviewer_view")
        if not isinstance(split_context, Mapping) or not isinstance(reviewer_view, Mapping):
            unresolved_packet_refs.append(
                {
                    "review_entity_qid": qid,
                    "reason": "packet_missing_required_review_fields",
                }
            )
            continue
        probe_rows.append(
            {
                "review_entity_qid": qid,
                "packet_id": _stringify(packet.get("packet_id")),
                "split_plan_id": _stringify(split_context.get("split_plan_id")),
                "packet_status": _stringify(split_context.get("status")),
                "recommended_next_step": _stringify(reviewer_view.get("recommended_next_step")),
                "uncertainty_flags": _string_list(reviewer_view.get("uncertainty_flags")),
                "smallest_typing_check": _smallest_typing_check(packet),
                "promotion_guard": _stringify(governance.get("promotion_guard", "hold")) or "hold",
                "execution_allowed": False,
                "cohort_flags": [MISSING_INSTANCE_OF_TYPING_FLAG],
            }
        )

    artifact_status = "review_only_ready" if not unresolved_packet_refs else "review_only_incomplete"
    typing_deficit_signals = [_build_probe_typing_signal(row) for row in probe_rows]
    return {
        "schema_version": WIKIDATA_NAT_COHORT_D_TYPE_PROBING_SURFACE_SCHEMA_VERSION,
        "lane_id": _stringify(cohort_d_review_surface.get("lane_id")),
        "cohort_id": _stringify(cohort_d_review_surface.get("cohort_id")),
        "artifact_status": artifact_status,
        "current_gate_id": _stringify(review_surface.get("current_gate_id")),
        "next_gate_id": _stringify(review_surface.get("next_gate_id")),
        "governance": {
            "automation_allowed": False,
            "can_execute_edits": False,
            "fail_closed": bool(governance.get("fail_closed", True)),
            "promotion_guard": _stringify(governance.get("promotion_guard", "hold")) or "hold",
        },
        "required_reviewer_checks": [
            {
                "check_id": _stringify(check.get("check_id")),
                "description": _stringify(check.get("description")),
            }
            for check in cohort_d_review_surface.get("required_reviewer_checks", [])
            if isinstance(check, Mapping)
        ],
        "probe_rows": probe_rows,
        "typing_deficit_signals": typing_deficit_signals,
        "surface_flags": [MISSING_INSTANCE_OF_TYPING_FLAG],
        "unresolved_packet_refs": unresolved_packet_refs,
        "non_claims": [
            "non_executing_type_probe_surface",
            "no_direct_migration_execution",
            "no_checked_safe_promotion_from_missing_instance_of_alone",
        ],
    }


def _priority_from_probe_row(row: Mapping[str, Any]) -> str:
    uncertainty_flags = set(_string_list(row.get("uncertainty_flags")))
    if "page_open_questions" in uncertainty_flags:
        return "high"
    if _stringify(row.get("packet_status")) == "review_only":
        return "high"
    return "medium"


def _build_operator_workflow_summary(
    *,
    readiness: str,
    queue_size: int,
    high_priority_count: int,
    medium_priority_count: int,
    unresolved_packet_ref_count: int,
    promotion_guard: str,
) -> dict[str, Any]:
    counts = {
        "queue_size": queue_size,
        "high_priority_count": high_priority_count,
        "medium_priority_count": medium_priority_count,
        "unresolved_packet_ref_count": unresolved_packet_ref_count,
    }
    if unresolved_packet_ref_count > 0 or readiness != "review_queue_ready":
        return {
            "stage": "inspect",
            "recommended_view": "unresolved_packet_refs",
            "reason": f"{unresolved_packet_ref_count} packet reference(s) still need resolution before clean review.",
            "counts": counts,
            "promotion_gate": {"decision": promotion_guard or "hold"},
        }
    if high_priority_count > 0:
        return {
            "stage": "follow_up",
            "recommended_view": "operator_queue",
            "reason": f"{high_priority_count} high-priority typing check(s) should be reviewed first.",
            "counts": counts,
            "promotion_gate": {"decision": promotion_guard or "hold"},
        }
    if queue_size > 0:
        return {
            "stage": "decide",
            "recommended_view": "operator_queue",
            "reason": f"{queue_size} queued packet(s) remain for bounded review.",
            "counts": counts,
            "promotion_gate": {"decision": promotion_guard or "hold"},
        }
    return {
        "stage": "record",
        "recommended_view": "summary",
        "reason": "No queued packet review remains on this operator surface.",
        "counts": counts,
        "promotion_gate": {"decision": promotion_guard or "hold"},
    }


def _build_control_index_workflow_summary(
    *,
    all_batches_ready: bool,
    batch_count: int,
    case_count: int,
    total_queue_size: int,
    total_unresolved_packet_ref_count: int,
    promotion_guard: str,
) -> dict[str, Any]:
    counts = {
        "batch_count": batch_count,
        "case_count": case_count,
        "total_queue_size": total_queue_size,
        "total_unresolved_packet_ref_count": total_unresolved_packet_ref_count,
    }
    if total_unresolved_packet_ref_count > 0 or not all_batches_ready:
        return {
            "stage": "inspect",
            "recommended_view": "batch_entries",
            "reason": (
                f"{total_unresolved_packet_ref_count} unresolved packet reference(s) and "
                f"{batch_count} batch(es) still need readiness review."
            ),
            "counts": counts,
            "promotion_gate": {"decision": promotion_guard or "hold"},
        }
    if total_queue_size > 0:
        return {
            "stage": "decide",
            "recommended_view": "batch_entries",
            "reason": f"{total_queue_size} queued packet review item(s) remain across {case_count} case(s).",
            "counts": counts,
            "promotion_gate": {"decision": promotion_guard or "hold"},
        }
    return {
        "stage": "record",
        "recommended_view": "summary",
        "reason": "All tracked cohort-D batches are ready and no queued review work remains.",
        "counts": counts,
        "promotion_gate": {"decision": promotion_guard or "hold"},
    }


def build_wikidata_nat_cohort_d_operator_review_surface(
    *,
    type_probing_surface: Mapping[str, Any],
) -> dict[str, Any]:
    probe_rows = type_probing_surface.get("probe_rows")
    governance = type_probing_surface.get("governance")
    if not isinstance(probe_rows, list):
        raise ValueError("type_probing_surface requires probe_rows")
    if not isinstance(governance, Mapping):
        raise ValueError("type_probing_surface requires governance")

    queue_rows: list[dict[str, Any]] = []
    for row in probe_rows:
        if not isinstance(row, Mapping):
            continue
        qid = _stringify(row.get("review_entity_qid")).strip()
        if not qid:
            continue
        queue_rows.append(
            {
                "review_entity_qid": qid,
                "packet_id": _stringify(row.get("packet_id")),
                "split_plan_id": _stringify(row.get("split_plan_id")),
                "priority": _priority_from_probe_row(row),
                "smallest_next_check": _stringify(row.get("smallest_typing_check")),
                "recommended_next_step": _stringify(row.get("recommended_next_step")),
                "uncertainty_flags": _string_list(row.get("uncertainty_flags")),
                "execution_allowed": False,
            }
        )

    queue_rows = sorted(
        queue_rows,
        key=lambda row: (0 if row["priority"] == "high" else 1, row["review_entity_qid"]),
    )

    unresolved_packet_refs = type_probing_surface.get("unresolved_packet_refs")
    unresolved_count = len(unresolved_packet_refs) if isinstance(unresolved_packet_refs, list) else 0
    readiness = "review_queue_ready" if unresolved_count == 0 else "review_queue_incomplete"

    return {
        "schema_version": WIKIDATA_NAT_COHORT_D_OPERATOR_REVIEW_SURFACE_SCHEMA_VERSION,
        "lane_id": _stringify(type_probing_surface.get("lane_id")),
        "cohort_id": _stringify(type_probing_surface.get("cohort_id")),
        "readiness": readiness,
        "queue_size": len(queue_rows),
        "unresolved_packet_ref_count": unresolved_count,
        "operator_queue": queue_rows,
        "required_checklist": [
            "confirm_absence_of_instance_of",
            "collect_typing_candidates",
            "record_reconcile_or_hold_decision",
        ],
        "governance": {
            "automation_allowed": False,
            "can_execute_edits": False,
            "fail_closed": bool(governance.get("fail_closed", True)),
            "promotion_guard": _stringify(governance.get("promotion_guard", "hold")) or "hold",
        },
        "non_claims": [
            "non_executing_operator_review_surface",
            "no_direct_migration_execution",
            "no_checked_safe_promotion_from_missing_instance_of_alone",
        ],
    }


def build_wikidata_nat_cohort_d_operator_report(
    operator_review_surface: Mapping[str, Any],
) -> dict[str, Any]:
    operator_queue = operator_review_surface.get("operator_queue")
    governance = operator_review_surface.get("governance")
    if not isinstance(operator_queue, list):
        raise ValueError("operator_review_surface requires operator_queue")
    if not isinstance(governance, Mapping):
        raise ValueError("operator_review_surface requires governance")

    high_priority_count = sum(
        1 for row in operator_queue
        if isinstance(row, Mapping) and _stringify(row.get("priority")) == "high"
    )
    medium_priority_count = sum(
        1 for row in operator_queue
        if isinstance(row, Mapping) and _stringify(row.get("priority")) == "medium"
    )
    unresolved_packet_ref_count = int(operator_review_surface.get("unresolved_packet_ref_count", 0) or 0)
    readiness = _stringify(operator_review_surface.get("readiness"))
    promotion_guard = _stringify(governance.get("promotion_guard", "hold")) or "hold"

    queue_preview: list[dict[str, Any]] = []
    triage_prompts: list[str] = []
    for row in operator_queue:
        if not isinstance(row, Mapping):
            continue
        qid = _stringify(row.get("review_entity_qid")).strip()
        if not qid:
            continue
        next_check = _stringify(row.get("smallest_next_check")).strip()
        priority = _stringify(row.get("priority")).strip() or "medium"
        queue_preview.append(
            {
                "review_entity_qid": qid,
                "priority": priority,
                "smallest_next_check": next_check,
                "recommended_next_step": _stringify(row.get("recommended_next_step")),
            }
        )
        triage_prompts.append(
            f"Review {qid} as {priority} priority; start with {next_check or 'confirm_absence_of_instance_of'}."
        )

    blocked_signals: list[str] = []
    if unresolved_packet_ref_count > 0:
        blocked_signals.append("unresolved_packet_refs_present")
    if readiness != "review_queue_ready":
        blocked_signals.append("operator_review_surface_not_ready")

    return {
        "schema_version": WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_SCHEMA_VERSION,
        "lane_id": _stringify(operator_review_surface.get("lane_id")),
        "cohort_id": _stringify(operator_review_surface.get("cohort_id")),
        "readiness": readiness,
        "decision": "review",
        "promotion_allowed": False,
        "summary": {
            "queue_size": len(queue_preview),
            "high_priority_count": high_priority_count,
            "medium_priority_count": medium_priority_count,
            "unresolved_packet_ref_count": unresolved_packet_ref_count,
        },
        "workflow_summary": _build_operator_workflow_summary(
            readiness=readiness,
            queue_size=len(queue_preview),
            high_priority_count=high_priority_count,
            medium_priority_count=medium_priority_count,
            unresolved_packet_ref_count=unresolved_packet_ref_count,
            promotion_guard=promotion_guard,
        ),
        "queue_preview": queue_preview,
        "triage_prompts": triage_prompts,
        "blocked_signals": blocked_signals,
        "governance": {
            "automation_allowed": False,
            "can_execute_edits": False,
            "fail_closed": bool(governance.get("fail_closed", True)),
            "promotion_guard": promotion_guard,
        },
        "non_claims": [
            "report_only_surface",
            "no_direct_migration_execution",
            "no_checked_safe_promotion_from_missing_instance_of_alone",
        ],
    }


def build_wikidata_nat_cohort_d_operator_report_batch(
    *,
    operator_review_surfaces: Sequence[Mapping[str, Any]],
    batch_id: str | None = None,
) -> dict[str, Any]:
    if not operator_review_surfaces:
        raise ValueError("operator_review_surfaces requires at least one surface")

    case_reports: list[dict[str, Any]] = []
    readiness_counts = {"review_queue_ready": 0, "review_queue_incomplete": 0}
    total_queue_size = 0
    total_high_priority = 0
    total_unresolved_packet_refs = 0
    blocked_signals: set[str] = set()

    for index, surface in enumerate(operator_review_surfaces, start=1):
        if not isinstance(surface, Mapping):
            continue
        report = build_wikidata_nat_cohort_d_operator_report(surface)
        case_id = _stringify(surface.get("case_id")).strip() or f"cohort_d_case_{index}"
        readiness = _stringify(report.get("readiness"))
        if readiness == "review_queue_ready":
            readiness_counts["review_queue_ready"] += 1
        else:
            readiness_counts["review_queue_incomplete"] += 1
        summary = report.get("summary", {})
        queue_size = int(summary.get("queue_size", 0) or 0)
        high_priority_count = int(summary.get("high_priority_count", 0) or 0)
        unresolved_count = int(summary.get("unresolved_packet_ref_count", 0) or 0)
        total_queue_size += queue_size
        total_high_priority += high_priority_count
        total_unresolved_packet_refs += unresolved_count
        blocked_signals.update(_string_list(report.get("blocked_signals")))
        case_reports.append(
            {
                "case_id": case_id,
                "lane_id": _stringify(report.get("lane_id")),
                "cohort_id": _stringify(report.get("cohort_id")),
                "readiness": readiness,
                "queue_size": queue_size,
                "high_priority_count": high_priority_count,
                "unresolved_packet_ref_count": unresolved_count,
                "decision": _stringify(report.get("decision")),
                "promotion_allowed": bool(report.get("promotion_allowed", False)),
            }
        )

    case_reports = sorted(case_reports, key=lambda case: case["case_id"])
    all_ready = readiness_counts["review_queue_incomplete"] == 0
    return {
        "schema_version": WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_BATCH_SCHEMA_VERSION,
        "batch_id": batch_id or "cohort_d_operator_report_batch",
        "decision": "review",
        "promotion_allowed": False,
        "summary": {
            "case_count": len(case_reports),
            "readiness_counts": readiness_counts,
            "total_queue_size": total_queue_size,
            "total_high_priority_count": total_high_priority,
            "total_unresolved_packet_ref_count": total_unresolved_packet_refs,
            "all_cases_ready": all_ready,
        },
        "case_reports": case_reports,
        "blocked_signals": sorted(blocked_signals),
        "non_claims": [
            "batch_report_only_surface",
            "no_direct_migration_execution",
            "no_checked_safe_promotion_from_missing_instance_of_alone",
        ],
    }


def build_wikidata_nat_cohort_d_review_control_index(
    *,
    batch_reports: Sequence[Mapping[str, Any]],
    index_id: str | None = None,
) -> dict[str, Any]:
    if not batch_reports:
        raise ValueError("batch_reports requires at least one batch report")

    batch_entries: list[dict[str, Any]] = []
    readiness_counts = {"review_queue_ready": 0, "review_queue_incomplete": 0}
    total_case_count = 0
    total_queue_size = 0
    total_unresolved_packet_ref_count = 0
    blocked_signals: set[str] = set()

    for index, batch in enumerate(batch_reports, start=1):
        if not isinstance(batch, Mapping):
            continue
        summary = batch.get("summary", {})
        if not isinstance(summary, Mapping):
            summary = {}
        batch_id = _stringify(batch.get("batch_id")).strip() or f"cohort_d_batch_{index}"
        batch_case_count = int(summary.get("case_count", 0) or 0)
        batch_queue_size = int(summary.get("total_queue_size", 0) or 0)
        batch_unresolved = int(summary.get("total_unresolved_packet_ref_count", 0) or 0)
        batch_all_ready = bool(summary.get("all_cases_ready", False))
        batch_readiness = "review_queue_ready" if batch_all_ready else "review_queue_incomplete"

        readiness_counts[batch_readiness] += 1
        total_case_count += batch_case_count
        total_queue_size += batch_queue_size
        total_unresolved_packet_ref_count += batch_unresolved
        blocked_signals.update(_string_list(batch.get("blocked_signals")))
        if not batch_all_ready:
            blocked_signals.add("batch_not_all_cases_ready")

        batch_entries.append(
            {
                "batch_id": batch_id,
                "readiness": batch_readiness,
                "case_count": batch_case_count,
                "queue_size": batch_queue_size,
                "unresolved_packet_ref_count": batch_unresolved,
                "decision": _stringify(batch.get("decision")) or "review",
                "promotion_allowed": bool(batch.get("promotion_allowed", False)),
            }
        )

    batch_entries = sorted(batch_entries, key=lambda row: row["batch_id"])
    all_batches_ready = readiness_counts["review_queue_incomplete"] == 0
    hold_signals = ["promotion_guard_hold_enforced"]
    if not all_batches_ready:
        hold_signals.append("incomplete_batch_present")
    if total_unresolved_packet_ref_count > 0:
        hold_signals.append("unresolved_packet_refs_present")
    promotion_guard = "hold"

    return {
        "schema_version": WIKIDATA_NAT_COHORT_D_REVIEW_CONTROL_INDEX_SCHEMA_VERSION,
        "index_id": index_id or "cohort_d_review_control_index",
        "decision": "review",
        "promotion_allowed": False,
        "summary": {
            "batch_count": len(batch_entries),
            "case_count": total_case_count,
            "total_queue_size": total_queue_size,
            "total_unresolved_packet_ref_count": total_unresolved_packet_ref_count,
            "readiness_counts": readiness_counts,
            "all_batches_ready": all_batches_ready,
        },
        "workflow_summary": _build_control_index_workflow_summary(
            all_batches_ready=all_batches_ready,
            batch_count=len(batch_entries),
            case_count=total_case_count,
            total_queue_size=total_queue_size,
            total_unresolved_packet_ref_count=total_unresolved_packet_ref_count,
            promotion_guard=promotion_guard,
        ),
        "batch_entries": batch_entries,
        "blocked_signals": sorted(blocked_signals),
        "hold_signals": hold_signals,
        "non_claims": [
            "control_index_only_surface",
            "no_direct_migration_execution",
            "no_checked_safe_promotion_from_missing_instance_of_alone",
        ],
    }


__all__ = [
    "WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_BATCH_SCHEMA_VERSION",
    "WIKIDATA_NAT_COHORT_D_REVIEW_CONTROL_INDEX_SCHEMA_VERSION",
    "WIKIDATA_NAT_COHORT_D_OPERATOR_REVIEW_SURFACE_SCHEMA_VERSION",
    "WIKIDATA_NAT_COHORT_D_OPERATOR_REPORT_SCHEMA_VERSION",
    "WIKIDATA_NAT_COHORT_D_TYPE_PROBING_SURFACE_SCHEMA_VERSION",
    "build_wikidata_nat_cohort_d_operator_report_batch",
    "build_wikidata_nat_cohort_d_review_control_index",
    "build_wikidata_nat_cohort_d_operator_report",
    "build_wikidata_nat_cohort_d_operator_review_surface",
    "build_wikidata_nat_cohort_d_type_probing_surface",
]
