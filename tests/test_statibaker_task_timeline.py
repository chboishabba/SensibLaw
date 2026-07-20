from __future__ import annotations

import json
from pathlib import Path

from src.statibaker_task_timeline import build_bidirectional_task_timeline_probe


def _fixture() -> dict:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "statibaker_kanban"
        / "archive_thread_timeline_probe_v0_1.json"
    )
    return json.loads(path.read_text())


def test_prior_prefix_is_folded_before_seed_interpretation() -> None:
    fixture = _fixture()
    probe = build_bidirectional_task_timeline_probe(
        timeline_cases=fixture["timeline_cases"],
        source=fixture["source"],
    )

    assert probe["schema_version"] == "sl.statibaker_bidirectional_task_timeline.v0_1"
    assert probe["timeline_count"] == fixture["expected"]["timeline_count"]
    assert probe["summary"]["seed_reinterpreted_with_prior_state"] == 10
    assert probe["authority_boundary"]["prior_prefix_is_folded_before_seed_interpretation"] is True
    assert probe["authority_boundary"]["later_suffix_is_folded_after_seed_interpretation"] is True

    by_title = {row["task_title"]: row for row in probe["timelines"]}
    phase4 = by_title["Resolve Phase-4 readiness blockers"]
    assert phase4["folded_prior_state"]["observed_slots"] == ["prior_phase_context"]
    assert phase4["seed_interpretation_state"]["observed_slots"] == [
        "blocker_list",
        "prior_phase_context",
    ]
    assert phase4["folded_final_state"]["observed_slots"] == [
        "blocker_diagnosis",
        "blocker_list",
        "prior_phase_context",
    ]
    assert phase4["final_task_status"] == "progressed_to_blocker_diagnosis"
    assert phase4["task_identity_residual"] == "exact"


def test_prior_event_can_prove_seed_is_not_task_origin() -> None:
    probe = build_bidirectional_task_timeline_probe(
        timeline_cases=[
            {
                "timeline_id": "timeline:reopen",
                "task_id": "task:signup",
                "task_title": "Fix signup flow",
                "canonical_thread_id": "thread:signup",
                "seed_role": "reopen_request",
                "seed_task_pnf": {
                    "predicate_family": "action",
                    "action_type": "fix",
                    "object": "signup flow",
                    "lifecycle_effect": "mark_in_progress",
                },
                "expected_event_slots": ["prior_completion", "failed_verification", "reopen"],
                "prior_event_receipts": [
                    {
                        "source_message_id": "m1",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "lifecycle_event_type": "completed",
                        "status_after": "done",
                        "expected_slot": "prior_completion",
                        "task_identity_evidence": "same signup-flow task had already completed",
                        "residual": "exact",
                    },
                    {
                        "source_message_id": "m2",
                        "timestamp": "2026-01-02T00:00:00+00:00",
                        "lifecycle_event_type": "failed_verification",
                        "expected_slot": "failed_verification",
                        "residual": "exact",
                    },
                ],
                "seed_message_receipt": {
                    "source_message_id": "m3",
                    "timestamp": "2026-01-02T00:05:00+00:00",
                    "lifecycle_event_type": "reopened",
                    "status_after": "in_progress",
                    "expected_slot": "reopen",
                    "residual": "exact",
                },
                "later_event_receipts": [],
            }
        ]
    )

    timeline = probe["timelines"][0]
    assert timeline["folded_prior_state"]["status"] == "done"
    assert timeline["seed_interpretation_state"]["status"] == "in_progress"
    assert timeline["final_task_status"] == "in_progress"
    assert timeline["task_identity_residual"] == "exact"
    assert timeline["missing_expected_slots"] == []


def test_missing_slots_are_computed_across_both_sides_of_seed() -> None:
    probe = build_bidirectional_task_timeline_probe(
        timeline_cases=[
            {
                "task_title": "Review deployment",
                "expected_event_slots": ["prior_patch", "review_request", "acceptance_test"],
                "prior_event_receipts": [
                    {
                        "lifecycle_event_type": "implemented",
                        "expected_slot": "prior_patch",
                        "residual": "exact",
                    }
                ],
                "seed_message_receipt": {
                    "lifecycle_event_type": "seed_candidate",
                    "expected_slot": "review_request",
                    "residual": "exact",
                },
                "later_event_receipts": [],
            }
        ]
    )

    timeline = probe["timelines"][0]
    assert timeline["matched_expected_slots"] == ["prior_patch", "review_request"]
    assert timeline["missing_expected_slots"] == ["acceptance_test"]
    assert timeline["lifecycle_residual"] == "incomplete"
