from __future__ import annotations

import json
import sys

from scripts import run_post_closure_probe as probe


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_probe_uses_legacy_finalization_refs_without_loading_families(
    monkeypatch,
    tmp_path,
) -> None:
    checkpoint_root = tmp_path / "checkpoints"
    finalization = checkpoint_root / "closure-finalization" / "document_test"
    finalization.mkdir(parents=True)
    _write_json(
        finalization / "materialized-reduction.manifest.json",
        {
            "owner_fingerprint": {"proposal_manifest_ref": "proposal:1"},
            "graph_ref": "graph:1",
            "proposal_count": 10,
            "deduplicated_count": 0,
            "factor_count": 2,
            "residual_count": 0,
        },
    )
    _write_json(
        finalization / "fixed-point-certificate.json",
        {
            "certificate": {
                "document_ref": "document:test",
                "revision": 7,
                "certificate_ref": "certificate:1",
                "ledger_ref": "ledger:1",
                "materialized_graph_ref": "graph:1",
                "local_fixed_point": "reached",
            }
        },
    )
    _write_json(finalization / "convergent-ledger.json", {"ledger_ref": "ledger:1"})
    _write_json(finalization / "region-boundary-summaries.json", {"summaries": []})
    (finalization / "materialized-factors.jsonl").write_text(
        '{"factor_ref":"factor:1"}\n{"factor_ref":"factor:2"}\n',
        encoding="utf-8",
    )
    (finalization / "materialized-residuals.jsonl").write_text("", encoding="utf-8")
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

    report = json.loads(
        (output / "post-closure-probe-report.json").read_text(encoding="utf-8")
    )
    receipt = json.loads(
        (output / "post-closure-reference-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["owner_object_transferred"] is False
    assert report["full_factor_payload_loaded"] is False
    assert report["full_residual_payload_loaded"] is False
    assert report["serializer"]["reference_only"] is True
    assert receipt["materialized_reduction"]["factor_path"].endswith(
        "materialized-factors.jsonl"
    )
    assert "factors" not in receipt["materialized_reduction"]
