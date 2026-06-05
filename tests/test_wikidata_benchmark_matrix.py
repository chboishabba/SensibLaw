from __future__ import annotations

import json
from pathlib import Path

from src.ontology.wikidata_benchmark_matrix import run_benchmark_matrix


def test_wikidata_benchmark_matrix_cache_only_default_fixture() -> None:
    report = run_benchmark_matrix()
    assert report["schema"] == "sensiblaw.wikidata_benchmark_matrix.v0_1"
    assert report["network_mode"] == "cache-only"
    assert report["status"] == "ok"
    assert {row["lane"] for row in report["lanes"]} == {"projection", "review", "live-cached", "hotspot-eval", "baseline-compare"}
    assert all(row["non_authoritative"] for row in report["lanes"])


def test_wikidata_benchmark_matrix_structural_drift_is_regression(tmp_path: Path) -> None:
    manifest = {
        "manifest_id": "drift",
        "lanes": {
            "projection": {
                "expected": {"structural_hash": "a", "provenance_count": 1, "disposition": "review", "non_authoritative": True},
                "observed": {"structural_hash": "b", "provenance_count": 1, "disposition": "review", "non_authoritative": True},
            }
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    report = run_benchmark_matrix(path, lanes=["projection"])
    assert report["status"] == "regression"
    assert report["lanes"][0]["issues"][0]["kind"] == "structural_hash"
