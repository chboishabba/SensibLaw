from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.runtime.bounded_document_scheduler import (
    BoundedDocumentScheduler,
    ScheduledJob,
    WorkClass,
)
from src.runtime.document_execution_policy import (
    DocumentExecutionPolicy,
    ResourceSnapshot,
)


MIB = 1024 * 1024


def _policy() -> DocumentExecutionPolicy:
    return DocumentExecutionPolicy(
        worker_budget=2,
        max_in_flight_jobs=2,
        queue_limit_bytes=16 * MIB,
        soft_memory_limit_bytes=100 * MIB,
        hard_memory_limit_bytes=140 * MIB,
        recovery_target_bytes=80 * MIB,
        max_compaction_attempts=2,
        minimum_recovery_bytes=10 * MIB,
    )


def test_scheduler_reassigns_workers_until_frontier_drains() -> None:
    admitted: list[str] = []

    def admit(job: ScheduledJob[int], result: int):
        admitted.append(job.job_ref)
        if result == 1:
            return (
                ScheduledJob(
                    "derived:1",
                    10,
                    WorkClass.CLOSURE_CONSUMER,
                    priority=1,
                ),
            )
        return ()

    def sample(queued: int, pending: int, in_flight: int) -> ResourceSnapshot:
        return ResourceSnapshot(
            rss_bytes=50 * MIB,
            process_tree_rss_bytes=50 * MIB,
            queued_bytes=queued,
            pending_jobs=pending,
            in_flight_jobs=in_flight,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        scheduler = BoundedDocumentScheduler(
            executor=pool,
            execute=lambda value: value,
            admit=admit,
            sample_resources=sample,
            compact=lambda: None,
            policy=_policy(),
        )
        scheduler.extend(
            (
                ScheduledJob("producer:1", 1, WorkClass.SEMANTIC_PRODUCER),
                ScheduledJob("producer:2", 2, WorkClass.SEMANTIC_PRODUCER),
                ScheduledJob("producer:3", 3, WorkClass.SEMANTIC_PRODUCER),
            )
        )
        receipt = scheduler.run()

    assert receipt.jobs_completed == 4
    assert receipt.peak_in_flight == 2
    assert receipt.bounded_stop is False
    assert set(admitted) == {
        "producer:1",
        "producer:2",
        "producer:3",
        "derived:1",
    }


def test_pressure_defers_producer_while_consumer_drains_then_restores_it() -> None:
    rss_values = iter((110, 75, 75, 75, 75, 75, 75, 75))
    compact_calls: list[bool] = []
    execution_order: list[str] = []

    def sample(queued: int, pending: int, in_flight: int) -> ResourceSnapshot:
        try:
            rss = next(rss_values)
        except StopIteration:
            rss = 75
        return ResourceSnapshot(
            rss_bytes=rss * MIB,
            process_tree_rss_bytes=rss * MIB,
            queued_bytes=queued,
            pending_jobs=pending,
            in_flight_jobs=in_flight,
        )

    jobs = (
        ScheduledJob(
            "producer",
            "producer",
            WorkClass.SEMANTIC_PRODUCER,
            priority=100,
        ),
        ScheduledJob(
            "consumer",
            "consumer",
            WorkClass.PERSISTENCE_CONSUMER,
            priority=1,
            criticality=10,
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        scheduler = BoundedDocumentScheduler(
            executor=pool,
            execute=lambda value: execution_order.append(value) or value,
            admit=lambda _job, _result: (),
            sample_resources=sample,
            compact=lambda: compact_calls.append(True),
            policy=_policy(),
        )
        scheduler.extend(jobs)
        receipt = scheduler.run()

    assert compact_calls == [True]
    assert execution_order[0] == "consumer"
    assert set(execution_order) == {"consumer", "producer"}
    assert receipt.jobs_deferred >= 1
    assert receipt.bounded_stop is False


def test_sustained_hard_pressure_returns_checkpointable_bounded_stop() -> None:
    checkpoints: list[dict[str, object]] = []

    def sample(queued: int, pending: int, in_flight: int) -> ResourceSnapshot:
        return ResourceSnapshot(
            rss_bytes=150 * MIB,
            process_tree_rss_bytes=150 * MIB,
            queued_bytes=queued,
            pending_jobs=pending,
            in_flight_jobs=in_flight,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        scheduler = BoundedDocumentScheduler(
            executor=pool,
            execute=lambda value: value,
            admit=lambda _job, _result: (),
            sample_resources=sample,
            compact=lambda: None,
            policy=_policy(),
            checkpoint=lambda decision, snapshot: checkpoints.append(
                {**decision.to_dict(), "snapshot": snapshot.to_dict()}
            ),
        )
        scheduler.extend(
            (ScheduledJob("producer", 1, WorkClass.SEMANTIC_PRODUCER),)
        )
        receipt = scheduler.run()

    assert receipt.bounded_stop is True
    assert receipt.jobs_completed == 0
    assert checkpoints
    assert checkpoints[-1]["bounded_stop"] is True
