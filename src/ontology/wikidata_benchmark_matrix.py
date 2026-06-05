from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


SCHEMA = "sensiblaw.wikidata_benchmark_matrix.v0_1"
LANES = ("projection", "review", "live-cached", "hotspot-eval", "baseline-compare")


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikidata" / "benchmark_matrix_v1" / "manifest.json"


def run_benchmark_matrix(
    manifest_path: Path | None = None,
    *,
    lanes: list[str] | None = None,
    network_mode: str = "cache-only",
) -> dict[str, Any]:
    if network_mode != "cache-only":
        if network_mode != "live-refresh":
            raise ValueError("network_mode must be cache-only or live-refresh")
    manifest_path = manifest_path or default_manifest_path()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = lanes or list(LANES)
    unknown = sorted(set(selected) - set(LANES))
    if unknown:
        raise ValueError(f"unknown benchmark lanes: {', '.join(unknown)}")
    started = time.perf_counter()
    lane_rows = [_evaluate_lane(lane, manifest, network_mode=network_mode) for lane in selected]
    regressions = [row for row in lane_rows if row["status"] == "regression"]
    return {
        "schema": SCHEMA,
        "manifest_id": manifest.get("manifest_id", "benchmark_matrix_v1"),
        "manifest_path": str(manifest_path),
        "network_mode": network_mode,
        "lane_count": len(lane_rows),
        "status": "regression" if regressions else "ok",
        "timing_drift_posture": "advisory",
        "runtime_ms": round((time.perf_counter() - started) * 1000, 6),
        "lanes": lane_rows,
    }


def _evaluate_lane(lane: str, manifest: dict[str, Any], *, network_mode: str) -> dict[str, Any]:
    fixture = dict((manifest.get("lanes") or {}).get(lane) or {})
    expected = dict(fixture.get("expected") or {})
    observed = dict(fixture.get("observed") or expected)
    issues: list[dict[str, Any]] = []
    for key in ("structural_hash", "provenance_count", "disposition", "non_authoritative"):
        if key in expected and observed.get(key) != expected.get(key):
            severity = "regression"
            if key == "provenance_count" and int(observed.get(key) or 0) >= int(expected.get(key) or 0):
                severity = "ok"
            if severity == "regression":
                issues.append({"kind": key, "expected": expected.get(key), "observed": observed.get(key)})
    timing = {
        "expected_ms": expected.get("runtime_ms"),
        "observed_ms": observed.get("runtime_ms"),
        "advisory": True,
    }
    if lane == "live-cached" and network_mode == "cache-only":
        observed["live_refresh"] = False
    return {
        "lane": lane,
        "status": "regression" if issues else "ok",
        "issues": issues,
        "timing": timing,
        "non_authoritative": bool(observed.get("non_authoritative", True)),
        "provenance_count": int(observed.get("provenance_count") or 0),
        "observed": observed,
    }
