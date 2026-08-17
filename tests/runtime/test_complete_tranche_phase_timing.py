from __future__ import annotations

from src.runtime.complete_tranche_phase_timing import CompleteTranchePhaseTimer


def _state(phase: str, receipt: str, *, token_count: int | None = None):
    detail = {} if token_count is None else {"token_count": token_count}
    return {
        "last_phase": phase,
        "last_receipt_ref": receipt,
        "phases": {
            phase: {
                "phase_ref": f"tranche-phase:{phase.lower()}:v0_2",
                "state": "completed",
                "detail": detail,
            }
        },
    }


def test_preexisting_checkpoint_is_not_charged_as_new_work() -> None:
    timer = CompleteTranchePhaseTimer()
    timer.prime(
        _state("SOURCE_INVENTORY", "old"),
        epoch_ns=1_000,
        monotonic_ns=10_000,
    )

    assert (
        timer.observe(
            _state("SOURCE_INVENTORY", "old"),
            epoch_ns=2_000,
            monotonic_ns=20_000,
        )
        is None
    )
    observed = timer.observe(
        _state("CANONICAL_PROJECTION", "new", token_count=2404),
        epoch_ns=3_000,
        monotonic_ns=30_000,
    )

    assert observed is not None
    assert observed.phase == "CANONICAL_PROJECTION"
    assert observed.wall_ns == 20_000
    assert observed.token_count_out == 2404


def test_phase_ranking_prefers_absolute_minutes_over_seconds() -> None:
    timer = CompleteTranchePhaseTimer()
    timer.prime(None, epoch_ns=0, monotonic_ns=0)
    timer.observe(
        _state("LOCAL_PNF_COMPILATION", "a"),
        epoch_ns=2_000_000_000,
        monotonic_ns=2_000_000_000,
    )
    timer.observe(
        _state("EXTERNAL_DEMAND_PLANNING", "b"),
        epoch_ns=122_000_000_000,
        monotonic_ns=122_000_000_000,
    )

    report = timer.report(tranche="GWB", process_returncode=0)

    assert [row["name"] for row in report["optimization_attention"]] == [
        "EXTERNAL_DEMAND_PLANNING",
        "LOCAL_PNF_COMPILATION",
    ]
    assert report["optimization_attention"][0]["horizon"] == "minutes"
    assert report["optimization_attention"][1]["horizon"] == "seconds"


def test_duplicate_checkpoint_poll_does_not_double_count_phase() -> None:
    timer = CompleteTranchePhaseTimer()
    timer.prime(None, epoch_ns=0, monotonic_ns=0)
    state = _state("LOCAL_WORLD_PROJECTION", "same")
    assert timer.observe(state, epoch_ns=100, monotonic_ns=100) is not None
    assert timer.observe(state, epoch_ns=200, monotonic_ns=200) is None
    assert len(timer.intervals) == 1
