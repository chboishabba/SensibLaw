from __future__ import annotations

import json
from pathlib import Path
import tarfile

from src.runtime.diagnostic_bundle import (
    bundle_artifact_directory,
    write_json_receipt,
)


def test_diagnostic_bundle_contains_receipt_and_existing_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "gate-a-run"
    nested = root / "timings"
    nested.mkdir(parents=True)
    (nested / "phase.txt").write_text("17.431s\n", encoding="utf-8")
    receipt = write_json_receipt(
        root,
        {"direct_total_ns": 123, "coverage_state": "complete"},
        filename="receipt-v2.json",
    )

    archive = bundle_artifact_directory(root)

    assert receipt.exists()
    assert archive == tmp_path / "gate-a-run.tar.xz"
    with tarfile.open(archive, mode="r:xz") as handle:
        names = set(handle.getnames())
        assert "gate-a-run/receipt-v2.json" in names
        assert "gate-a-run/timings/phase.txt" in names
        payload = json.load(handle.extractfile("gate-a-run/receipt-v2.json"))
        assert payload["coverage_state"] == "complete"
