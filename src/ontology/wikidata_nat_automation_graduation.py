from __future__ import annotations

from typing import Any, Mapping, Sequence


AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_eval.v0_1"
AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_report.v0_1"
AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_batch_report.v0_1"
AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_evidence_report.v0_1"
AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION = "sl.wikidata_nat_automation_graduation_governance_index.v0_1"
AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION = (
    "sl.wikidata_nat_automation_graduation_governance_summary.v0_1"
)


def _as_text_set(values: Sequence[Any] | None) -> set[str]:
    if values is None:
        return set()
    normalized: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text:
            normalized.add(text)
    return normalized


def _as_text(value: Any) -> str:
    return str(value).strip()


def _find_gate(criteria: Mapping[str, Any], gate_id: str) -> Mapping[str, Any] | None:
    gates = criteria.get("gates", [])
    if not isinstance(gates, Sequence):
        return None
    for gate in gates:
        if isinstance(gate, Mapping) and _as_text(gate.get("gate_id")) == gate_id:
            return gate
    return None


def evaluate_nat_automation_promotion(
    criteria: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Deterministic fail-closed evaluator for Nat automation-graduation proposals.

    Required proposal fields:
    - gate_id
    - from_level
    - to_level
    - gate_families_passed (list[str])
    - evidence_signals (list[str])
    - risk_signals (list[str])
    - metrics (mapping[str, Any])
    - recommendation (promote|hold|revert)
    """
    failed_checks: list[str] = []
    gate_id = _as_text(proposal.get("gate_id"))
    gate = _find_gate(criteria, gate_id)
    if gate is None:
        failed_checks.append("gate_not_found")
        return {
            "schema_version": AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
            "status": "rejected",
            "gate_id": gate_id,
            "decision": "hold",
            "promotion_allowed": False,
            "failed_checks": failed_checks,
        }

    expected_from = int(gate.get("from_level", -1))
    expected_to = int(gate.get("to_level", -1))
    proposal_from = int(proposal.get("from_level", -1))
    proposal_to = int(proposal.get("to_level", -1))
    if proposal_from != expected_from or proposal_to != expected_to:
        failed_checks.append("level_transition_mismatch")

    recommendation = _as_text(proposal.get("recommendation")).lower()
    if recommendation not in {"promote", "hold", "revert"}:
        failed_checks.append("invalid_recommendation")

    required_families = _as_text_set(criteria.get("gate_families_required"))
    passed_families = _as_text_set(proposal.get("gate_families_passed"))
    missing_families = sorted(required_families - passed_families)
    if missing_families:
        failed_checks.append("missing_required_gate_families")

    must_show = _as_text_set(gate.get("must_show"))
    evidence_signals = _as_text_set(proposal.get("evidence_signals"))
    missing_must_show = sorted(must_show - evidence_signals)
    if missing_must_show:
        failed_checks.append("missing_must_show_evidence")

    blocked_signals = _as_text_set(gate.get("blocked_if"))
    risk_signals = _as_text_set(proposal.get("risk_signals"))
    triggered_blockers = sorted(blocked_signals & risk_signals)
    if triggered_blockers:
        failed_checks.append("blocked_signal_triggered")

    required_metrics = _as_text_set(criteria.get("metrics_required"))
    metrics = proposal.get("metrics", {})
    provided_metrics: set[str] = set()
    if isinstance(metrics, Mapping):
        provided_metrics = _as_text_set(list(metrics.keys()))
    else:
        failed_checks.append("metrics_not_mapping")
    missing_metrics = sorted(required_metrics - provided_metrics)
    if missing_metrics:
        failed_checks.append("missing_required_metrics")

    fail_closed = bool(failed_checks)
    promotion_allowed = not fail_closed
    status = "approved" if promotion_allowed and recommendation == "promote" else "held"
    if fail_closed:
        status = "rejected"

    decision = "promote" if status == "approved" else "hold"
    return {
        "schema_version": AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION,
        "status": status,
        "gate_id": gate_id,
        "from_level": proposal_from,
        "to_level": proposal_to,
        "decision": decision,
        "promotion_allowed": promotion_allowed,
        "failed_checks": sorted(set(failed_checks)),
        "missing_gate_families": missing_families,
        "missing_must_show": missing_must_show,
        "triggered_blockers": triggered_blockers,
        "missing_metrics": missing_metrics,
    }


def build_nat_automation_graduation_report(
    criteria: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = evaluate_nat_automation_promotion(criteria, proposal)
    proposal_id = _as_text(proposal.get("proposal_id"))
    lane = _as_text(criteria.get("lane"))
    return {
        "schema_version": AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION,
        "lane": lane,
        "proposal_id": proposal_id,
        "gate_id": evaluation.get("gate_id", ""),
        "decision": evaluation["decision"],
        "status": evaluation["status"],
        "promotion_allowed": evaluation["promotion_allowed"],
        "failed_checks": evaluation["failed_checks"],
        "summary": {
            "missing_gate_families": evaluation.get("missing_gate_families", []),
            "missing_must_show": evaluation.get("missing_must_show", []),
            "triggered_blockers": evaluation.get("triggered_blockers", []),
            "missing_metrics": evaluation.get("missing_metrics", []),
        },
        "evaluation": evaluation,
    }


def build_nat_automation_graduation_batch_report(
    criteria: Mapping[str, Any],
    proposal_batch: Mapping[str, Any],
) -> dict[str, Any]:
    proposals_raw = proposal_batch.get("proposals", [])
    reports: list[dict[str, Any]] = []
    if isinstance(proposals_raw, Sequence):
        for proposal in proposals_raw:
            if isinstance(proposal, Mapping):
                reports.append(build_nat_automation_graduation_report(criteria, proposal))

    approved_count = sum(1 for report in reports if report.get("status") == "approved")
    held_count = sum(1 for report in reports if report.get("status") == "held")
    rejected_count = sum(1 for report in reports if report.get("status") == "rejected")
    fail_closed_count = sum(1 for report in reports if not bool(report.get("promotion_allowed")))

    return {
        "schema_version": AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "batch_id": _as_text(proposal_batch.get("batch_id")),
        "proposal_count": len(reports),
        "summary": {
            "approved_count": approved_count,
            "held_count": held_count,
            "rejected_count": rejected_count,
            "fail_closed_count": fail_closed_count,
        },
        "reports": reports,
    }


def build_nat_automation_graduation_evidence_report(
    criteria: Mapping[str, Any],
    proposal_batches: Mapping[str, Any],
    *,
    min_runs: int = 2,
) -> dict[str, Any]:
    raw_runs = proposal_batches.get("runs", [])
    batch_reports: list[dict[str, Any]] = []
    if isinstance(raw_runs, Sequence):
        for index, run in enumerate(raw_runs):
            if not isinstance(run, Mapping):
                continue
            report = build_nat_automation_graduation_batch_report(criteria, run)
            report_with_run = dict(report)
            report_with_run["run_id"] = _as_text(run.get("run_id")) or f"run-{index + 1}"
            batch_reports.append(report_with_run)

    run_count = len(batch_reports)
    proposal_count = sum(int(report.get("proposal_count", 0)) for report in batch_reports)
    approved_count = sum(int(report.get("summary", {}).get("approved_count", 0)) for report in batch_reports)
    held_count = sum(int(report.get("summary", {}).get("held_count", 0)) for report in batch_reports)
    rejected_count = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in batch_reports)
    fail_closed_count = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in batch_reports)

    all_gate_ids = {
        _as_text(item.get("gate_id"))
        for report in batch_reports
        for item in report.get("reports", [])
        if isinstance(item, Mapping) and _as_text(item.get("gate_id"))
    }
    consistency_gate_id = next(iter(all_gate_ids), "")
    gate_consistent = len(all_gate_ids) <= 1

    failed_reasons: list[str] = []
    if run_count < max(int(min_runs), 1):
        failed_reasons.append("insufficient_repeated_runs")
    if proposal_count <= 0:
        failed_reasons.append("no_proposals_evaluated")
    if rejected_count > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_count > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if held_count > 0:
        failed_reasons.append("held_proposals_present")
    if not gate_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "evidence_batch_id": _as_text(proposal_batches.get("evidence_batch_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "readiness_scope": {
            "min_runs": max(int(min_runs), 1),
            "run_count": run_count,
            "proposal_count": proposal_count,
            "gate_consistent": gate_consistent,
            "gate_id": consistency_gate_id,
        },
        "summary": {
            "approved_count": approved_count,
            "held_count": held_count,
            "rejected_count": rejected_count,
            "fail_closed_count": fail_closed_count,
        },
        "run_reports": batch_reports,
    }


def build_nat_automation_graduation_governance_index(
    criteria: Mapping[str, Any],
    evidence_snapshots: Mapping[str, Any],
    *,
    min_snapshots: int = 2,
) -> dict[str, Any]:
    raw_snapshots = evidence_snapshots.get("snapshots", [])
    reports: list[dict[str, Any]] = []
    if isinstance(raw_snapshots, Sequence):
        for index, snapshot in enumerate(raw_snapshots):
            if not isinstance(snapshot, Mapping):
                continue
            snapshot_id = _as_text(snapshot.get("snapshot_id")) or f"snapshot-{index + 1}"
            if isinstance(snapshot.get("evidence_report"), Mapping):
                report = dict(snapshot["evidence_report"])
            elif isinstance(snapshot.get("proposal_batches"), Mapping):
                report = build_nat_automation_graduation_evidence_report(
                    criteria,
                    snapshot["proposal_batches"],
                    min_runs=int(snapshot.get("min_runs", 2)),
                )
            else:
                report = {
                    "schema_version": AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "readiness_failed_reasons": ["snapshot_missing_evidence_payload"],
                    "readiness_scope": {"gate_id": "", "run_count": 0},
                    "summary": {
                        "approved_count": 0,
                        "held_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                }
            report["snapshot_id"] = snapshot_id
            reports.append(report)

    snapshot_count = len(reports)
    ready_count = sum(1 for report in reports if bool(report.get("promotion_ready")))
    not_ready_count = snapshot_count - ready_count
    rejected_total = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in reports)
    fail_closed_total = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in reports)

    gate_ids = {
        _as_text(report.get("readiness_scope", {}).get("gate_id"))
        for report in reports
        if _as_text(report.get("readiness_scope", {}).get("gate_id"))
    }
    gate_scope_consistent = len(gate_ids) <= 1
    gate_id = next(iter(gate_ids), "")

    failed_reasons: list[str] = []
    if snapshot_count < max(int(min_snapshots), 1):
        failed_reasons.append("insufficient_snapshot_count")
    if snapshot_count <= 0:
        failed_reasons.append("no_snapshots_evaluated")
    if not_ready_count > 0:
        failed_reasons.append("not_ready_snapshots_present")
    if rejected_total > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_total > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if not gate_scope_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "governance_batch_id": _as_text(evidence_snapshots.get("governance_batch_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "scope": {
            "min_snapshots": max(int(min_snapshots), 1),
            "snapshot_count": snapshot_count,
            "gate_scope_consistent": gate_scope_consistent,
            "gate_id": gate_id,
        },
        "summary": {
            "ready_count": ready_count,
            "not_ready_count": not_ready_count,
            "rejected_count": rejected_total,
            "fail_closed_count": fail_closed_total,
        },
        "snapshot_reports": reports,
    }


def build_nat_automation_graduation_governance_summary(
    criteria: Mapping[str, Any],
    governance_snapshots: Mapping[str, Any],
    *,
    min_indexes: int = 2,
) -> dict[str, Any]:
    raw_snapshots = governance_snapshots.get("snapshots", [])
    reports: list[dict[str, Any]] = []
    if isinstance(raw_snapshots, Sequence):
        for index, snapshot in enumerate(raw_snapshots):
            if not isinstance(snapshot, Mapping):
                continue
            snapshot_id = _as_text(snapshot.get("snapshot_id")) or f"governance-snapshot-{index + 1}"
            if isinstance(snapshot.get("governance_index"), Mapping):
                report = dict(snapshot["governance_index"])
            elif isinstance(snapshot.get("evidence_snapshots"), Mapping):
                report = build_nat_automation_graduation_governance_index(
                    criteria,
                    snapshot["evidence_snapshots"],
                    min_snapshots=int(snapshot.get("min_snapshots", 2)),
                )
            else:
                report = {
                    "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION,
                    "status": "not_ready",
                    "decision": "hold",
                    "promotion_ready": False,
                    "readiness_failed_reasons": ["snapshot_missing_governance_payload"],
                    "scope": {"gate_id": "", "snapshot_count": 0},
                    "summary": {
                        "ready_count": 0,
                        "not_ready_count": 0,
                        "rejected_count": 0,
                        "fail_closed_count": 0,
                    },
                }
            report["snapshot_id"] = snapshot_id
            reports.append(report)

    index_count = len(reports)
    ready_count = sum(1 for report in reports if bool(report.get("promotion_ready")))
    not_ready_count = index_count - ready_count
    rejected_total = sum(int(report.get("summary", {}).get("rejected_count", 0)) for report in reports)
    fail_closed_total = sum(int(report.get("summary", {}).get("fail_closed_count", 0)) for report in reports)

    gate_ids = {
        _as_text(report.get("scope", {}).get("gate_id"))
        for report in reports
        if _as_text(report.get("scope", {}).get("gate_id"))
    }
    gate_scope_consistent = len(gate_ids) <= 1
    gate_id = next(iter(gate_ids), "")

    failed_reasons: list[str] = []
    if index_count < max(int(min_indexes), 1):
        failed_reasons.append("insufficient_governance_index_count")
    if index_count <= 0:
        failed_reasons.append("no_governance_indexes_evaluated")
    if not_ready_count > 0:
        failed_reasons.append("not_ready_governance_indexes_present")
    if rejected_total > 0:
        failed_reasons.append("rejected_proposals_present")
    if fail_closed_total > 0:
        failed_reasons.append("fail_closed_proposals_present")
    if not gate_scope_consistent:
        failed_reasons.append("mixed_gate_scope")

    promotion_ready = not failed_reasons
    decision = "promote" if promotion_ready else "hold"
    status = "ready" if promotion_ready else "not_ready"

    return {
        "schema_version": AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION,
        "lane": _as_text(criteria.get("lane")),
        "governance_summary_id": _as_text(governance_snapshots.get("governance_summary_id")),
        "status": status,
        "decision": decision,
        "promotion_ready": promotion_ready,
        "readiness_failed_reasons": sorted(set(failed_reasons)),
        "scope": {
            "min_indexes": max(int(min_indexes), 1),
            "index_count": index_count,
            "gate_scope_consistent": gate_scope_consistent,
            "gate_id": gate_id,
        },
        "summary": {
            "ready_count": ready_count,
            "not_ready_count": not_ready_count,
            "rejected_count": rejected_total,
            "fail_closed_count": fail_closed_total,
        },
        "governance_reports": reports,
    }


__all__ = [
    "AUTOMATION_GRADUATION_EVAL_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_BATCH_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_EVIDENCE_REPORT_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_INDEX_SCHEMA_VERSION",
    "AUTOMATION_GRADUATION_GOVERNANCE_SUMMARY_SCHEMA_VERSION",
    "build_nat_automation_graduation_batch_report",
    "build_nat_automation_graduation_evidence_report",
    "build_nat_automation_graduation_governance_index",
    "build_nat_automation_graduation_governance_summary",
    "build_nat_automation_graduation_report",
    "evaluate_nat_automation_promotion",
]
