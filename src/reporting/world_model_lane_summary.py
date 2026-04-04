"""Shared reporting over rebound world-model lane artifacts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.reporting.governance_gate import (
    LaneGovernanceSnapshot,
    evaluate_multi_lane_gate,
)


WORLD_MODEL_LANE_SUMMARY_SCHEMA_VERSION = "sl.world_model_lane_summary.v0_1"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def build_lane_governance_snapshot(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValueError("world-model lane summary requires mapping reports")

    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    claims = _as_list(report.get("claims"))
    lane_name = (
        _as_text(report.get("lane_id"))
        or _as_text(report.get("family_id"))
        or _as_text(report.get("packet_id"))
        or "unknown_lane"
    )

    claim_count = int(summary.get("claim_count") or len(claims))
    must_review_count = int(summary.get("must_review_count") or 0)
    must_abstain_count = int(summary.get("must_abstain_count") or 0)
    can_act_count = sum(
        1
        for claim in claims
        if _as_text((claim.get("action_policy") or {}).get("actionability")) == "can_act"
    )
    can_recommend_count = sum(
        1
        for claim in claims
        if _as_text((claim.get("action_policy") or {}).get("actionability")) == "can_recommend"
    )

    decision = "hold"
    if can_act_count > 0:
        decision = "promote"
    elif must_review_count > 0 and must_abstain_count == 0:
        decision = "audit"

    snapshot = LaneGovernanceSnapshot(
        lane_name=lane_name,
        promotion_gate_decision=decision,
        authority_receipt_count=claim_count,
        follow_queue_open=must_review_count + must_abstain_count,
        unresolved_pressure_status="open" if (must_review_count + must_abstain_count) else "clear",
    )
    return {
        "lane_name": snapshot.lane_name,
        "promotion_gate_decision": snapshot.promotion_gate_decision,
        "authority_receipt_count": snapshot.authority_receipt_count,
        "follow_queue_open": snapshot.follow_queue_open,
        "unresolved_pressure_status": snapshot.unresolved_pressure_status,
        "metrics": {
            "claim_count": claim_count,
            "must_review_count": must_review_count,
            "must_abstain_count": must_abstain_count,
            "can_act_count": can_act_count,
            "can_recommend_count": can_recommend_count,
        },
    }


def build_world_model_lane_summary(
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    snapshots = [build_lane_governance_snapshot(report) for report in reports if isinstance(report, Mapping)]
    gate = evaluate_multi_lane_gate(
        [
            LaneGovernanceSnapshot(
                lane_name=_as_text(snapshot.get("lane_name")),
                promotion_gate_decision=_as_text(snapshot.get("promotion_gate_decision")),
                authority_receipt_count=int(snapshot.get("authority_receipt_count") or 0),
                follow_queue_open=int(snapshot.get("follow_queue_open") or 0),
                unresolved_pressure_status=_as_text(snapshot.get("unresolved_pressure_status")) or None,
            )
            for snapshot in snapshots
        ]
    )
    return {
        "schema_version": WORLD_MODEL_LANE_SUMMARY_SCHEMA_VERSION,
        "lane_snapshots": snapshots,
        "summary": {
            "lane_count": len(snapshots),
            "ready_lane_count": gate.ready_lane_count,
            "total_authority_receipts": gate.total_authority_receipts,
            "open_follow_conjectures": gate.open_follow_conjectures,
        },
        "governance_gate": {
            "decision": gate.decision,
            "ready_lanes": list(gate.ready_lanes),
            "gating_thresholds": dict(gate.gating_thresholds),
        },
    }
