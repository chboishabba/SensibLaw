from __future__ import annotations

from src.runtime.checkpoint_retention import (
    ArtifactRetentionClass,
    CheckpointRetentionLedger,
)


def test_retention_never_reclaims_authoritative_checkpoint(tmp_path) -> None:
    authoritative = tmp_path / "factors.jsonl"
    diagnostic = tmp_path / "events.jsonl"
    authoritative.write_bytes(b"authoritative")
    diagnostic.write_bytes(b"diagnostic")
    ledger = CheckpointRetentionLedger(root=tmp_path, budget_bytes=1)
    ledger.register(
        authoritative,
        retention_class=ArtifactRetentionClass.AUTHORITATIVE_REUSABLE,
    )
    ledger.register(
        diagnostic,
        retention_class=ArtifactRetentionClass.DIAGNOSTIC,
        successor_ref="receipt:complete",
    )

    result = ledger.reclaim(required_bytes=diagnostic.stat().st_size)

    assert authoritative.exists()
    assert not diagnostic.exists()
    assert result["removed"] == [str(diagnostic.resolve())]


def test_derived_checkpoint_requires_successor_before_reclaim(tmp_path) -> None:
    derived = tmp_path / "derived.json"
    derived.write_text("{}", encoding="utf-8")
    ledger = CheckpointRetentionLedger(root=tmp_path, budget_bytes=1)
    ledger.register(
        derived,
        retention_class=ArtifactRetentionClass.DERIVED_REPRODUCIBLE,
    )

    first = ledger.reclaim(required_bytes=2)
    ledger.mark_superseded(derived, successor_ref="manifest:v2")
    second = ledger.reclaim(required_bytes=2)

    assert first["removed"] == []
    assert second["removed"] == [str(derived.resolve())]
