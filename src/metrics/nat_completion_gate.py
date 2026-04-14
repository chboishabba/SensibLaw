from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "wikidata"
    / "wikidata_nat_cohort_a_gate_b_candidate_verification_runs_ready_20260403.json"
)


def load_nat_completion_fixture() -> Dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def candidate_yield(report: Dict[str, Any]) -> int:
    return len(report.get("candidate_ids", []))


def dry_run_pass_rate(report: Dict[str, Any]) -> float:
    runs = report.get("runs", [])
    if not runs:
        return 0.0
    verified_counts = sum(
        1
        for run in runs
        if report.get("expected_summary", {}).get("verified_candidate_count_per_run")
        == len(run.get("migration_pack", {}).get("candidates", []))
    )
    return verified_counts / len(runs)


def live_verification_pass_rate(report: Dict[str, Any]) -> float:
    summary = report.get("expected_summary", {})
    total = summary.get("run_count") or 0
    verified = summary.get("counts_by_status", {}).get("verified", 0)
    if total == 0:
        return 0.0
    return verified / (total * summary.get("verified_candidate_count_per_run", 1))


def data_loss_zero(report: Dict[str, Any]) -> bool:
    for run in report.get("runs", []):
        for candidate in run.get("migration_pack", {}).get("candidates", []):
            before = candidate.get("claim_bundle_before", {}).get("value")
            after = candidate.get("claim_bundle_after", {}).get("value")
            if before != after:
                return False
    return True


def idempotency_score(report: Dict[str, Any]) -> float:
    runs = report.get("runs", [])
    if len(runs) < 2:
        return 0.0
    sets = []
    for run in runs:
        candidates = run.get("migration_pack", {}).get("candidates", [])
        sets.append({candidate.get("candidate_id") for candidate in candidates})
    if not sets:
        return 0.0
    intersection = set.intersection(*sets)
    union = set.union(*sets)
    return len(intersection) / len(union) if union else 0.0


def scorecard(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_yield": candidate_yield(report),
        "dry_run_pass_rate": dry_run_pass_rate(report),
        "live_verification_pass_rate": live_verification_pass_rate(report),
        "data_loss_zero": data_loss_zero(report),
        "idempotency_score": idempotency_score(report),
    }
