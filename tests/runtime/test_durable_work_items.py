from __future__ import annotations

from pathlib import Path

from src.runtime.durable_work_items import DurableWorkSpec


def _spec(tmp_path: Path, **overrides: object) -> DurableWorkSpec:
    values: dict[str, object] = {
        "database_url": "postgresql://example/test",
        "run_ref": "run:1",
        "document_ref": "document:1",
        "stage_contract_ref": "typing:v1",
        "operation_ref": "local-type-carrier",
        "partition_ref": "leaf:7",
        "ordinal": 7,
        "input_manifest": {
            "stage_input_identity": {"source": "sha256:abc"},
            "leaf_input_identity": {"start": 70, "end": 80},
        },
        "artifact_root": tmp_path,
        "worker_ref": "worker:1",
    }
    values.update(overrides)
    return DurableWorkSpec(**values)  # type: ignore[arg-type]


def test_work_identity_is_deterministic_and_machine_independent(tmp_path: Path) -> None:
    first = _spec(tmp_path / "machine-a", worker_ref="worker:a")
    second = _spec(tmp_path / "machine-b", worker_ref="worker:b")

    assert first.work_ref == second.work_ref
    assert first.stage_instance_ref == second.stage_instance_ref
    assert first.input_sha256 == second.input_sha256


def test_work_identity_changes_with_semantic_input(tmp_path: Path) -> None:
    first = _spec(tmp_path)
    second = _spec(
        tmp_path,
        input_manifest={
            "stage_input_identity": {"source": "sha256:abc"},
            "leaf_input_identity": {"start": 80, "end": 90},
        },
    )

    assert first.work_ref != second.work_ref
    assert first.input_sha256 != second.input_sha256
    assert first.stage_instance_ref == second.stage_instance_ref


def test_round_trip_preserves_execution_only_fields(tmp_path: Path) -> None:
    spec = _spec(tmp_path)

    restored = DurableWorkSpec.from_dict(spec.to_dict())

    assert restored == spec
    assert restored.work_ref == spec.work_ref
