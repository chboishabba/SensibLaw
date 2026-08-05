from __future__ import annotations

from pathlib import Path

from src.policy.durable_work_item_execution import TYPING_STAGE_CONTRACT
from src.runtime.durable_work_item_hardening import complete_leased_work
from src.runtime.durable_work_items import DurableWorkSpec


def test_typing_contract_is_explicit() -> None:
    assert TYPING_STAGE_CONTRACT == "postgres-durable-typing-leaf:v1"


def test_artifact_rows_are_work_scoped() -> None:
    source = Path(complete_leased_work.__code__.co_filename).read_text(encoding="utf-8")

    assert '"work_ref": spec.work_ref' in source
    assert '"content_sha256": output_digest.hex()' in source
    assert "state = 'leased'" in source
    assert "lease_token = %s" in source
    assert "lease_epoch = %s" in source


def test_work_identity_excludes_worker_and_machine_paths(tmp_path: Path) -> None:
    base = dict(
        database_url="postgresql://example/test",
        run_ref="run:1",
        document_ref="doc:1",
        stage_contract_ref="stage:v1",
        operation_ref="operation",
        partition_ref="leaf:1",
        ordinal=1,
        input_manifest={"stage_input_identity": {"source": "abc"}, "leaf": 1},
        lease_seconds=30,
    )
    first = DurableWorkSpec(
        **base,
        artifact_root=tmp_path / "a",
        worker_ref="worker:a",
    )
    second = DurableWorkSpec(
        **base,
        artifact_root=tmp_path / "b",
        worker_ref="worker:b",
    )

    assert first.work_ref == second.work_ref
    assert first.stage_instance_ref == second.stage_instance_ref
