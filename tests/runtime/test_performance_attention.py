from __future__ import annotations

from src.runtime.performance_attention import (
    MeasuredPhase,
    rank_optimization_attention,
    wall_horizon,
)


def test_longest_absolute_phase_outranks_easier_second_scale_kernel() -> None:
    ranked = rank_optimization_attention(
        (
            MeasuredPhase("hierarchy", 3_170_000_000),
            MeasuredPhase("coordinator", 1_250_000_000),
            MeasuredPhase("legacy_replay", 72 * 60 * 1_000_000_000, False),
        )
    )

    assert [item.name for item in ranked] == [
        "legacy_replay",
        "hierarchy",
        "coordinator",
    ]
    assert ranked[0].horizon == "hours"
    assert ranked[0].first_question == "remove_or_bypass_from_production"


def test_minutes_phase_outranks_large_percentage_subsecond_opportunity() -> None:
    ranked = rank_optimization_attention(
        (
            MeasuredPhase("minute_phase", 5 * 60 * 1_000_000_000),
            MeasuredPhase("tiny_phase", 900_000_000),
        )
    )

    assert ranked[0].name == "minute_phase"
    assert ranked[0].horizon == "minutes"
    assert ranked[1].horizon == "subsecond"


def test_wall_horizon_boundaries() -> None:
    assert wall_horizon(3_600_000_000_000) == "hours"
    assert wall_horizon(60_000_000_000) == "minutes"
    assert wall_horizon(1_000_000_000) == "seconds"
    assert wall_horizon(999_999_999) == "subsecond"
