from __future__ import annotations

import json

import pytest

from src.policy.artifact_projection import (
    ArtifactProjectionPolicy,
    InMemoryArtifactManifestReader,
    project_artifacts,
)
from src.runtime import execution_resource_ledger as ledger_module
from src.runtime.execution_resource_ledger import (
    ExecutionResourceLedger,
    build_ownership_report,
    compare_ownership_reports,
)


def test_sample_records_fallback_resources_and_monotonic_counters(monkeypatch):
    monkeypatch.setattr(ledger_module, "_proc_bytes", lambda _name: None)
    monkeypatch.setattr(ledger_module, "_rss_bytes", lambda: 1234)
    ledger = ExecutionResourceLedger(run_ref="trial:1", document_ref="document:1")

    first = ledger.sample("compile", semantic_counts={"sentences": 1})
    second = ledger.sample("compile", semantic_counts={"sentences": 2})

    assert first.rss_bytes == first.pss_bytes == first.uss_bytes == 1234
    assert first.resource_source == "resource_rusage_fallback"
    assert second.sequence == first.sequence + 1
    assert second.elapsed_ns >= first.elapsed_ns
    with pytest.raises(ValueError, match="semantic counter decreased"):
        ledger.sample("compile", semantic_counts={"sentences": 1})


def test_manifest_batches_are_bounded_and_telemetry_does_not_materialise():
    rows = [{"index": index} for index in range(513)]
    source = {"canonical_token_rows": rows}
    ledger = ExecutionResourceLedger(run_ref="trial:1")
    projected, reader = project_artifacts(
        source, policy=ArtifactProjectionPolicy.production(), resource_ledger=ledger
    )
    assert isinstance(reader, InMemoryArtifactManifestReader)

    batches = list(reader.iter_records("canonical_token_rows"))
    assert [len(batch) for batch in batches] == [256, 256, 1]
    assert projected["canonical_token_rows"]["record_count"] == 513
    assert all(
        sample.batch_rows <= 256 for sample in ledger.samples if sample.phase == "batch"
    )
    assert reader._sources["canonical_token_rows"] is rows


def test_reports_are_deterministic_and_comparison_never_selects_owner(monkeypatch):
    monkeypatch.setattr(
        ledger_module,
        "sample_process_resources",
        lambda: {
            "rss_bytes": 1000,
            "pss_bytes": 900,
            "uss_bytes": 800,
            "kernel": "test-kernel",
            "resource_source": "test",
        },
    )
    ledger = ExecutionResourceLedger(
        run_ref="trial:1",
        document_ref="document:1",
        environment={"fingerprint": "same"},
    )
    ledger.sample("before")
    ledger.sample("peak", batch_rows=256)
    ledger.sample("after", collect_gc=True)
    report = build_ownership_report(ledger)
    assert report["sample_count"] == 3
    assert report["classification"] == "retained_or_unresolved"
    comparison = compare_ownership_reports([report, report, report])
    assert comparison["matching_identity"] is True
    assert comparison["optimisation_owner"] is None
    assert comparison["threshold_selected"] is False
    assert json.loads(json.dumps(report, sort_keys=True)) == report
