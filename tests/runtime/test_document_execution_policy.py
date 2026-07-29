from __future__ import annotations

from src.runtime.document_execution_policy import (
    DocumentExecutionPolicy,
    DocumentRetentionPolicy,
    MemoryPressureController,
    PressureState,
    ResourceSnapshot,
    RetentionMode,
    relieve_memory_pressure,
)


MIB = 1024 * 1024


def _snapshot(rss_mib: int) -> ResourceSnapshot:
    return ResourceSnapshot(
        rss_bytes=rss_mib * MIB,
        process_tree_rss_bytes=rss_mib * MIB,
    )


def _policy() -> DocumentExecutionPolicy:
    return DocumentExecutionPolicy(
        worker_budget=4,
        max_in_flight_jobs=4,
        queue_limit_bytes=32 * MIB,
        soft_memory_limit_bytes=100 * MIB,
        hard_memory_limit_bytes=140 * MIB,
        recovery_target_bytes=80 * MIB,
        max_compaction_attempts=2,
        minimum_recovery_bytes=10 * MIB,
    )


def test_soft_limit_defers_producers_before_stopping() -> None:
    controller = MemoryPressureController(_policy())

    first = controller.observe(_snapshot(110))

    assert first.state is PressureState.COMPACTING
    assert first.defer_producers is True
    assert first.prioritise_consumers is True
    assert first.compact is True
    assert first.bounded_stop is False


def test_pressure_relief_recovers_without_bounded_stop() -> None:
    controller = MemoryPressureController(_policy())
    samples = iter((_snapshot(110), _snapshot(75)))
    compact_calls: list[bool] = []

    decision, final = relieve_memory_pressure(
        controller=controller,
        snapshot=next(samples),
        compact=lambda: compact_calls.append(True),
        resample=lambda: next(samples),
    )

    assert compact_calls == [True]
    assert final.rss_bytes == 75 * MIB
    assert decision.state is PressureState.NORMAL
    assert decision.bounded_stop is False


def test_hard_limit_stops_only_after_relief_attempts_do_not_shrink() -> None:
    controller = MemoryPressureController(_policy())

    first = controller.observe(_snapshot(150))
    second = controller.observe(_snapshot(150))
    third = controller.observe(_snapshot(150))

    assert first.compact is True
    assert second.compact is True
    assert third.state is PressureState.BOUNDED_STOP
    assert third.bounded_stop is True
    assert third.checkpoint is True


def test_shrinking_footprint_resets_compaction_attempts() -> None:
    controller = MemoryPressureController(_policy())
    controller.observe(_snapshot(130))
    shrinking = controller.observe(_snapshot(115))

    assert shrinking.state is PressureState.RECOVERING
    assert shrinking.bounded_stop is False
    assert shrinking.reason == "pressure relief is shrinking the footprint"


def test_producer_leases_are_suspended_but_consumers_can_drain() -> None:
    policy = _policy()

    producer = policy.lease_limit(
        in_flight_jobs=1,
        queued_bytes=0,
        pressure_state=PressureState.THROTTLED,
        producer=True,
    )
    consumer = policy.lease_limit(
        in_flight_jobs=1,
        queued_bytes=0,
        pressure_state=PressureState.THROTTLED,
        producer=False,
    )

    assert producer == 0
    assert consumer == 3


def test_production_retention_is_compact_by_default() -> None:
    policy = DocumentRetentionPolicy(mode=RetentionMode.PRODUCTION_COMPACT)

    assert policy.completed_jobs is False
    assert policy.full_receipts is False
    assert policy.state_deltas is False
    assert policy.observation_bodies is False


def test_audit_retention_preserves_full_history() -> None:
    policy = DocumentRetentionPolicy(mode=RetentionMode.AUDIT_FULL)

    assert policy.completed_jobs is True
    assert policy.full_receipts is True
    assert policy.state_deltas is True
    assert policy.observation_bodies is True
