from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "benchmarks" / "numeric-reuse" / "2026-08-16-v1.json"
LOCALITY_RECORD = ROOT / "benchmarks" / "numeric-reuse" / "2026-08-17-v2.json"
MANIFEST = ROOT / "data" / "benchmarks" / "numeric_reuse_v1" / "manifest.json"


def test_numeric_reuse_benchmark_record_preserves_pinned_evidence() -> None:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert record["schema_version"] == "sensiblaw.numeric-reuse-benchmark-record.v1"
    assert record["fixture"]["fixture_id"] == manifest["fixture_id"]
    assert (
        record["fixture"]["manifest_sha256"]
        == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    )
    assert record["outcomes"]["cold"]["accepted"]
    assert record["outcomes"]["exact_replay"]["receipt_equal_to_cold"]
    assert record["outcomes"]["exact_replay"]["receipt_loaded_without_reconstruction"]
    assert not record["outcomes"]["small_edit"]["leaf_dependency_locality_claim"]
    assert "truenas.local" not in RECORD.read_text(encoding="utf-8")


def test_leaf_locality_record_preserves_an_indeterminate_result() -> None:
    record = json.loads(LOCALITY_RECORD.read_text(encoding="utf-8"))

    locality = record["outcomes"]["small_edit"]["locality"]
    assert record["execution_commit"] == "7c5272fa4bb956e3fe63c84e522053e233093d95"
    assert record["outcomes"]["exact_replay"]["receipt_loaded_without_reconstruction"]
    assert locality["state"] == "indeterminate"
    assert not locality["claim_made"]
    assert "truenas.local" not in LOCALITY_RECORD.read_text(encoding="utf-8")
