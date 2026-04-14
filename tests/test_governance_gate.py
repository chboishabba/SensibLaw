from __future__ import annotations

from src.reporting.governance_gate import (
    LaneGovernanceSnapshot,
    evaluate_multi_lane_gate,
)


def test_evaluate_multi_lane_gate_holds_until_thresholds_are_met() -> None:
    summary = evaluate_multi_lane_gate(
        [
            LaneGovernanceSnapshot(
                lane_name="nat",
                promotion_gate_decision="promote",
                authority_receipt_count=2,
                follow_queue_open=4,
            ),
            LaneGovernanceSnapshot(
                lane_name="au",
                promotion_gate_decision="hold",
                authority_receipt_count=1,
                follow_queue_open=3,
            ),
        ]
    )

    assert summary.decision == "hold"
    assert summary.ready_lane_count == 1
    assert summary.total_authority_receipts == 3
    assert summary.open_follow_conjectures == 7
    assert summary.ready_lanes == ("nat",)


def test_evaluate_multi_lane_gate_goes_when_multi_lane_thresholds_pass() -> None:
    summary = evaluate_multi_lane_gate(
        [
            LaneGovernanceSnapshot(
                lane_name="nat",
                promotion_gate_decision="promote",
                authority_receipt_count=3,
                follow_queue_open=2,
            ),
            LaneGovernanceSnapshot(
                lane_name="au",
                promotion_gate_decision="audit",
                authority_receipt_count=2,
                follow_queue_open=3,
            ),
            LaneGovernanceSnapshot(
                lane_name="reviewer_packet",
                promotion_gate_decision="hold",
                authority_receipt_count=1,
                follow_queue_open=1,
            ),
        ]
    )

    assert summary.decision == "go"
    assert summary.ready_lane_count == 2
    assert summary.total_authority_receipts == 6
    assert summary.open_follow_conjectures == 6
    assert summary.ready_lanes == ("nat", "au")
    assert summary.gating_thresholds == {
        "required_ready_lanes": 2,
        "min_total_receipts": 5,
        "max_open_conjectures": 10,
    }
