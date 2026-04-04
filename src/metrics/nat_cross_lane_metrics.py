from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class NatCrossLaneMetrics:
    total_runs: int
    verified_runs: int
    drift_runs: int
    total_claims: int
    verified_claims: int
    pending_drift_run_ids: list[str]


def collect_nat_cross_lane_metrics(
    verification_reports: Sequence[Mapping[str, Any]],
) -> NatCrossLaneMetrics:
    total_runs = 0
    verified_runs = 0
    drift_runs = 0
    total_claims = 0
    verified_claims = 0
    pending_drift_run_ids: list[str] = []

    for report in verification_reports:
        if not isinstance(report, Mapping):
            continue
        total_runs += int(report.get("summary", {}).get("run_count", 0))
        verified_runs += int(report.get("summary", {}).get("verified_run_count", 0))
        pending_drift_run_ids.extend(report.get("summary", {}).get("pending_drifts", []))
        drift_runs += len(report.get("runs", [])) - int(report.get("summary", {}).get("verified_run_count", 0))
        total_claims += int(report.get("summary", {}).get("total_claims", 0))
        for run in report.get("runs", []):
            counts = run.get("counts_by_status", {})
            verified_claims += int(counts.get("verified", 0))

    return NatCrossLaneMetrics(
        total_runs=total_runs,
        verified_runs=verified_runs,
        drift_runs=drift_runs,
        total_claims=total_claims,
        verified_claims=verified_claims,
        pending_drift_run_ids=list(dict.fromkeys(str(value) for value in pending_drift_run_ids if value)),
    )
