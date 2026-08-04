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


@pytest.mark.parametrize(
    ("stage", "family"),
    (
        ("owner_admission_batch", "closure"),
        ("owner-admission-batch:leaf-12", "closure"),
        ("activation_result_collection", "closure"),
        ("activation_checkpoint_verification", "closure"),
        ("job_payload_construction", "closure"),
        ("job_identity_digesting", "closure"),
        ("job_canonical_sort", "closure"),
        ("job_deduplication", "closure"),
        ("owner_key_projection", "closure"),
        ("dirty_group_reduction", "closure"),
        ("ready_frontier_construction", "closure"),
        ("scheduled_job_submission", "closure"),
        ("base_proposal_reduction", "closure"),
        ("composition_generation", "closure"),
        ("composition_proposal_reduction", "closure"),
        ("local_typing_diagnostics:mention_licensing", "typing"),
        ("release_owner_state", "finalization"),
        ("isolated_serializer_started", "serialization"),
        ("publication_commit", "publication"),
        ("reference_parity_manifest", "parity"),
    ),
)
def test_semantic_substages_resolve_to_explicit_budget_family(
    stage: str,
    family: str,
) -> None:
    resolved = budget.budget_for_stage(stage)

    assert budget.stage_family(stage) == family
    assert resolved is not None
    assert resolved.stage_family == family


def test_required_semantic_stage_fails_closed_when_unmapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(
        budget,
        "sample_process_resources",
        lambda: {
            "rss_bytes": 1_000,
            "pss_bytes": 900,
            "uss_bytes": 800,
            "resource_source": "test",
            "kernel": "test",
        },
    )
    guard = budget.StageMemoryBudgetGuard(root=tmp_path)

    with pytest.raises(budget.StageMemoryBudgetMissing) as captured:
        guard.checkpoint(
            "new_unclassified_semantic_kernel",
            phase="running",
            require_budget=True,
        )

    assert captured.value.receipt["state"] == "unbudgeted"
    assert captured.value.receipt["budget_required"] is True
    latest = json.loads(
        (tmp_path / "stage-memory" / "latest.json").read_text(encoding="utf-8")
    )
    assert latest["stage"] == "new_unclassified_semantic_kernel"
    assert latest["state"] == "unbudgeted"
