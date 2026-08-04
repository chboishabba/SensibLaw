from __future__ import annotations

import json

import pytest

from src.runtime import stage_memory_budget as budget


def test_stage_budget_records_soft_pressure(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(
        budget,
        "sample_process_resources",
        lambda: {
            "rss_bytes": 4_500,
            "pss_bytes": 4_500,
            "uss_bytes": 4_000,
            "resource_source": "test",
            "kernel": "test",
        },
    )
    monkeypatch.setattr(
        budget,
        "DEFAULT_STAGE_BUDGETS",
        {"serialization": budget.StageMemoryBudget("serialization", 4_000, 5_000)},
    )
    guard = budget.StageMemoryBudgetGuard(root=tmp_path)

    receipt = guard.checkpoint("serialize_closure_receipt", phase="running")

    assert receipt["state"] == "soft_pressure"
    assert receipt["headroom_bytes"] == 500
    latest = json.loads(
        (tmp_path / "stage-memory" / "latest.json").read_text(encoding="utf-8")
    )
    assert latest["stage_family"] == "serialization"


def test_stage_budget_fails_below_global_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        budget,
        "sample_process_resources",
        lambda: {
            "rss_bytes": 6_000,
            "pss_bytes": 6_000,
            "uss_bytes": 5_500,
            "resource_source": "test",
            "kernel": "test",
        },
    )
    monkeypatch.setattr(
        budget,
        "DEFAULT_STAGE_BUDGETS",
        {"publication": budget.StageMemoryBudget("publication", 4_000, 5_000)},
    )

    with pytest.raises(budget.StageMemoryBudgetExceeded) as captured:
        budget.StageMemoryBudgetGuard().checkpoint(
            "postgres_persistence",
            phase="before_batch",
        )

    assert captured.value.receipt["state"] == "hard_exceeded"
