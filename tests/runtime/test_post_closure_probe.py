from __future__ import annotations

import sys

import pytest

from scripts import run_post_closure_probe as probe
from src.runtime.reference_receipt import atomic_write_binary


def test_probe_uses_typed_finalization_refs_without_loading_families(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    finalization = checkpoint_root / "closure-finalization" / "document_test"
    finalization.mkdir(parents=True)
    factor_path = finalization / "materialized-factors.bin"
    residual_path = finalization / "materialized-residuals.bin"
    factor_path.write_bytes(b"factor-family")
    residual_path.write_bytes(b"")
    reduction = {
        "owner_fingerprint": {"proposal_manifest_ref": "proposal:1"},
        "graph_ref": "graph:1",
        "proposal_count": 10,
        "deduplicated_count": 0,
        "factor_count": 2,
        "residual_count": 0,
        "factor_path": str(factor_path),
        "residual_path": str(residual_path),
    }
    atomic_write_binary(finalization / "materialized-reduction.manifest.pkl", reduction)
    atomic_write_binary(
        finalization / "closure-reference-receipt.spec.pkl",
        {
            "document_ref": "document:test",
            "revision": 7,
            "certificate_ref": "certificate:1",
            "ledger_ref": "ledger:1",
            "materialized_reduction": reduction,
        },
    )
    output = tmp_path / "probe-output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_post_closure_probe.py",
            "--checkpoint-root",
            str(checkpoint_root),
            "--output-root",
            str(output),
            "--serializer-hard-mib",
            "512",
            "--disk-budget-mib",
            "64",
        ],
    )

    assert probe.main() == 0

    report = probe._mapping(output / "post-closure-probe-report.pkl")
    receipt = probe._mapping(output / "post-closure-reference-receipt.pkl")
    assert report["owner_object_transferred"] is False
    assert report["full_factor_payload_loaded"] is False
    assert report["full_residual_payload_loaded"] is False
    assert report["serializer"]["reference_only"] is True
    assert receipt["materialized_reduction"]["factor_path"].endswith(
        "materialized-factors.bin"
    )
    assert "factors" not in receipt["materialized_reduction"]


def test_probe_rejects_legacy_text_finalization_authority(tmp_path) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    finalization = checkpoint_root / "closure-finalization" / "document_test"
    finalization.mkdir(parents=True)
    (finalization / "materialized-reduction.manifest.json").write_text(
        "{}", encoding="utf-8"
    )

    with pytest.raises(FileNotFoundError, match="legacy text checkpoints"):
        probe._find_finalization_root(checkpoint_root)
