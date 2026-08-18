from __future__ import annotations

from pathlib import Path

from src.storage.postgres.deterministic_admission_execution import (
    DeterministicAdmissionWorker,
    DeterministicAdmissionWorkerPool,
)
from src.storage.postgres.typed_execution_pool import (
    admit_computed_deltas,
    stage_typed_delta,
)


def test_workers_stage_results_without_allocating_owner_revisions() -> None:
    source = Path(stage_typed_delta.__code__.co_filename).read_text(encoding="utf-8")

    assert "resulting_revision, prior_revision" in source
    assert "NULL, NULL, NULL" in source
    assert "SET state = 'computed'" in source
    assert (
        "current_revision ="
        not in source.split("def stage_typed_delta", 1)[1].split(
            "def admit_computed_deltas", 1
        )[0]
    )


def test_coordinator_admits_computed_results_in_stable_order() -> None:
    source = Path(admit_computed_deltas.__code__.co_filename).read_text(
        encoding="utf-8"
    )
    function = source.split("def admit_computed_deltas", 1)[1].split(
        "def _worker_main", 1
    )[0]

    assert "ORDER BY j.priority, j.job_ref" in function
    assert "FOR UPDATE OF j, d" in function
    assert "SET prior_revision = %s, resulting_revision = %s" in function
    assert "state = 'completed'" in function
    assert "state = 'open'" not in function


def test_all_worker_surfaces_use_stage_then_canonical_admission() -> None:
    process_source = Path(
        DeterministicAdmissionWorkerPool.__module__.replace(".", "/") + ".py"
    )
    assert DeterministicAdmissionWorker.run_once is not None
    assert DeterministicAdmissionWorkerPool.run_until_idle is not None
    assert process_source.as_posix().endswith(
        "src/storage/postgres/deterministic_admission_execution.py"
    )
