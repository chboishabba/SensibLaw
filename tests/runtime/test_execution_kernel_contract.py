from __future__ import annotations

import pytest

from src.runtime.execution_kernel_contract import (
    KernelContractViolation,
    KernelRegistry,
)


def test_owner_handoff_requires_postgres_authority_evidence() -> None:
    registry = KernelRegistry()

    with pytest.raises(KernelContractViolation) as captured:
        registry.observe(
            stage="owner_admission_batch",
            phase="closure_handoff",
            counts={
                "rows_in": 2,
                "owner_revision": 4,
                "durable_admissions": 0,
                "new_durable_obligations": 1,
            },
            details={
                "batch_size": 2,
                "frontier_drained": False,
                "authority_backend": "checkpoint",
                "authority_row_count": 0,
            },
            budget_family="closure",
        )

    assert captured.value.diagnostic["violation"] == "postgresql_authority_missing"


def test_post_drain_admission_requires_new_durable_obligation() -> None:
    registry = KernelRegistry()

    with pytest.raises(KernelContractViolation) as captured:
        registry.observe(
            stage="owner_admission_batch",
            phase="closure_handoff",
            counts={
                "rows_in": 1,
                "owner_revision": 12,
                "durable_admissions": 12,
                "new_durable_obligations": 0,
            },
            details={
                "batch_size": 1,
                "frontier_drained": True,
                "authority_backend": "postgresql",
                "authority_row_count": 12,
            },
            budget_family="closure",
        )

    assert (
        captured.value.diagnostic["violation"]
        == "post_drain_admission_without_durable_obligation"
    )


def test_post_drain_admission_with_durable_obligation_is_explicit_progress() -> None:
    registry = KernelRegistry()

    event = registry.observe(
        stage="owner_admission_batch",
        phase="closure_handoff",
        counts={
            "rows_in": 1,
            "owner_revision": 13,
            "durable_admissions": 13,
            "new_durable_obligations": 1,
        },
        details={
            "batch_size": 1,
            "frontier_drained": True,
            "authority_backend": "postgresql",
            "authority_row_count": 13,
        },
        budget_family="closure",
    )

    assert event["kernel_key"] == "closure.handoff"
    assert event["progress"] == 13
    assert event["new_durable_obligations"] == 1
    assert event["violation"] is None


def test_wait_must_name_reason_and_dependency() -> None:
    registry = KernelRegistry()

    with pytest.raises(KernelContractViolation) as captured:
        registry.observe(
            stage="local_typing_diagnostics:local_type_carrier_build",
            phase="typing_parent_waiting",
            counts={"leaves_completed": 2, "leaves_total": 3},
            details={"wait_reason": "worker_results"},
            budget_family="typing",
        )

    assert captured.value.diagnostic["violation"] == "unnamed_wait"


def test_monotonic_typing_progress_and_named_wait_are_valid() -> None:
    registry = KernelRegistry()
    first = registry.observe(
        stage="local_typing_diagnostics:local_type_carrier_build",
        phase="typing_leaf_completed",
        counts={"leaves_completed": 1, "leaves_total": 3},
        details={"batch_size": 128},
        budget_family="typing",
    )
    waiting = registry.observe(
        stage="local_typing_diagnostics:local_type_carrier_build",
        phase="typing_parent_waiting",
        counts={"leaves_completed": 1, "leaves_total": 3},
        details={
            "wait_reason": "worker_results",
            "wait_dependency": "local_type_carrier_build",
        },
        budget_family="typing",
    )
    final = registry.observe(
        stage="local_typing_diagnostics:local_type_carrier_build",
        phase="typing_leaf_completed",
        counts={"leaves_completed": 2, "leaves_total": 3},
        details={"batch_size": 128},
        budget_family="typing",
    )

    assert first["progress"] == 1
    assert waiting["violation"] is None
    assert final["progress"] == 2
