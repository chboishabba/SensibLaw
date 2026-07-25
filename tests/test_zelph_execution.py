from __future__ import annotations

from src.zelph_execution import assess_zelph_execution


def test_zelph_execution_outcomes() -> None:
    unavailable = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload=None,
        required_predicates=("au_procedural_fact",),
    )
    assert unavailable.outcome == "engine_unavailable"
    assert unavailable.successful_handoff is False

    failed = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload={"status": "failed", "errors": ["boom"]},
        required_predicates=("au_procedural_fact",),
    )
    assert failed.outcome == "engine_failed"

    no_match = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload={"status": "ok", "results": []},
        required_predicates=(),
    )
    assert no_match.outcome == "executed_no_match"

    missing = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload={
            "status": "ok",
            "results": [
                {"predicate": "needs_review", "triple_ref": "triple:1"}
            ],
        },
        required_predicates=("au_procedural_fact",),
    )
    assert missing.outcome == "failed_required_output"
    assert missing.ok is False

    emitted = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload={
            "status": "ok",
            "results": [
                {
                    "predicate": "au_procedural_fact",
                    "triple_ref": "triple:2",
                }
            ],
        },
        required_predicates=("au_procedural_fact",),
    )
    assert emitted.outcome == "executed_with_output"
    assert emitted.successful_handoff is True
    assert emitted.ok is True


def test_blocked_input_never_invokes_success_contract() -> None:
    blocked = assess_zelph_execution(
        profile_ref="profile:au",
        engine_payload={"status": "ok", "results": []},
        required_predicates=("au_procedural_fact",),
        input_block_reasons=("missing-facts",),
    )
    assert blocked.outcome == "blocked_input"
    assert blocked.successful_handoff is False
