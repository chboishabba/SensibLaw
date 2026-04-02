from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.ontology.wikidata_review_packet_variant_compare import (
    compare_review_packet_variants,
)

AxisCandidate = Mapping[str, Any]


def build_cohort_e_diagnostic_report(
    *,
    primary_candidate: AxisCandidate,
    reference_candidates: Sequence[AxisCandidate],
    lane_id: str = "wikidata_nat_cohort_e_unreconciled_instanceof",
    max_comparisons: int = 3,
) -> dict[str, Any]:
    """Produce a bounded diagnostics surface for Cohort E unreconciled axes."""
    variant_surface = compare_review_packet_variants(
        primary_variant=primary_candidate,
        comparison_variants=reference_candidates,
        max_variants=max_comparisons,
    )
    return {
        "lane_id": lane_id,
        "primary_candidate_id": variant_surface["primary_candidate_id"],
        "comparisons": variant_surface["comparisons"],
        "diagnostic_flags": variant_surface["diagnostic_flags"],
        "hold_reason": "unreconciled instance of",
        "non_authoritative": True,
    }


def summarize_cohort_e_reports(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate agreement/disagreement counts across a diagnostics batch."""
    total = len(reports)
    agreement = disagreement = 0
    axis_disagreements: dict[str, int] = {}
    for report in reports:
        for comparison in report.get("comparisons", []):
            if comparison.get("status") == "agreement":
                agreement += 1
            else:
                disagreement += 1
                for axis in comparison.get("disagreements", []):
                    axis_disagreements[axis] = axis_disagreements.get(axis, 0) + 1
    return {
        "lane_id": reports[0]["lane_id"] if reports else "wikidata_nat_cohort_e_unreconciled_instanceof",
        "batch_size": total,
        "agreement_rows": agreement,
        "disagreement_rows": disagreement,
        "axis_disagreement_counts": axis_disagreements,
        "non_authoritative": True,
    }


__all__ = ["build_cohort_e_diagnostic_report", "summarize_cohort_e_reports"]
