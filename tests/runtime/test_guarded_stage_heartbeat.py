import json
import time
from contextlib import contextmanager
from pathlib import Path

from src.runtime.active_document_resources import (
    ActiveDocumentResourceGuard,
    GuardedDocumentProgress,
)


class _Progress:
    @contextmanager
    def stage(self, stage: str, **_kwargs):
        class Handle:
            active_stage = stage

            def observe(self, **_values):
                return None

        yield Handle()


def test_guarded_stage_emits_live_owner_heartbeats(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_ALL", "1")
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS", "0.01")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "8192")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "16384")

    guard = ActiveDocumentResourceGuard(document_ref="document:heartbeat")
    with guard.stage(_Progress(), "numeric_pnf_compilation"):
        guard.set_active_kernel("hierarchy_materialization")
        time.sleep(0.04)

    rows = [
        json.loads(line)
        for line in (tmp_path / "document_heartbeat.partial-timing.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    kernels = [row["current_kernel"] for row in rows]
    assert kernels[0] == "stage_boundary_before"
    assert "hierarchy_materialization" in kernels
    assert kernels[-1] == "stage_boundary_after"
    heartbeats = [
        row for row in rows if row["current_kernel"] == "hierarchy_materialization"
    ]
    assert all(row["partial_timing"]["acceptance_eligible"] is False for row in heartbeats)
    assert all(row["partial_timing"]["partial_run_evidence"] is True for row in heartbeats)


def test_zero_heartbeat_interval_disables_periodic_samples(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_ALL", "1")
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS", "0")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "8192")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "16384")

    guard = ActiveDocumentResourceGuard(document_ref="document:no-heartbeat")
    with guard.stage(_Progress(), "numeric_pnf_compilation"):
        guard.set_active_kernel("sentence_adjacency")
        time.sleep(0.02)

    rows = [
        json.loads(line)
        for line in (tmp_path / "document_no-heartbeat.partial-timing.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["current_kernel"] for row in rows] == [
        "stage_boundary_before",
        "stage_boundary_after",
    ]


def test_inner_progress_observation_reaches_guarded_timing_stream(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_ALL", "1")
    monkeypatch.setenv("SENSIBLAW_RESOURCE_CHECKPOINT_DIR", str(tmp_path))
    monkeypatch.setenv("SENSIBLAW_RESOURCE_HEARTBEAT_SECONDS", "0")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_SOFT_MEMORY_MIB", "8192")
    monkeypatch.setenv("SENSIBLAW_DOCUMENT_HARD_MEMORY_MIB", "16384")

    guard = ActiveDocumentResourceGuard(document_ref="document:inner-owner")
    progress = GuardedDocumentProgress(_Progress(), guard)
    with progress.stage("numeric_pnf_compilation") as handle:
        handle.observe(
            details={
                "current_kernel": "hierarchy_materialization",
                "completed": 3,
            }
        )

    rows = [
        json.loads(line)
        for line in (tmp_path / "document_inner-owner.partial-timing.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert any(
        row["current_kernel"] == "hierarchy_materialization" for row in rows
    )
    owner_rows = [
        row for row in rows if row["current_kernel"] == "hierarchy_materialization"
    ]
    assert owner_rows[-1]["persisted_counts"]["completed"] == 3
