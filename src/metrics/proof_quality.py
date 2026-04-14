from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ProofMetricResult:
    total_artifacts: int
    queue_readability_share: float
    proof_ready_share: float
    title_quality_score: float
    live_follow_share: float
    fallback_follow_share: float
    duplicate_pressure: int
    duplicate_density: float
    status_counts: Mapping[str, int]
    priority_coverage_share: float
    plateau_flag: bool


def compute_proof_quality_metrics(
    artifact_counts: Iterable[Mapping[str, object]],
    *,
    previous_ready_count: int | None = None,
) -> ProofMetricResult:
    total = 0
    ready = 0
    title_scores: list[float] = []
    live_follows = 0
    fallback_follows = 0
    duplicates = 0
    readable_statuses = 0
    status_counts: Counter[str] = Counter()
    priority_count = 0
    for row in artifact_counts:
        total += 1
        if row.get("status") == "proof_ready":
            ready += 1
        title_score = float(row.get("title_quality", 0) or 0)
        title_scores.append(min(max(title_score, 0.0), 1.0))
        if row.get("follow_source") == "live":
            live_follows += 1
        if row.get("duplicate_of"):
            duplicates += 1
        if row.get("follow_source") == "fallback":
            fallback_follows += 1
        status = row.get("status")
        if status:
            readable_statuses += 1
            status_counts[status] += 1
        if row.get("priority") is not None:
            priority_count += 1
    if total == 0:
        return ProofMetricResult(
            0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0,
            0.0,
            {},
            0.0,
            False,
        )
    plateau_flag = False
    if previous_ready_count is not None and previous_ready_count >= ready and ready > 0:
        plateau_flag = True
    return ProofMetricResult(
        total_artifacts=total,
        queue_readability_share=readable_statuses / total,
        proof_ready_share=ready / total,
        title_quality_score=sum(title_scores) / len(title_scores),
        live_follow_share=live_follows / total,
        fallback_follow_share=fallback_follows / total,
        duplicate_pressure=duplicates,
        duplicate_density=duplicates / total,
        status_counts=dict(status_counts),
        priority_coverage_share=priority_count / total,
        plateau_flag=plateau_flag,
    )
