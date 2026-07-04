from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.fact_intake.au_review_bundle import build_au_fact_review_bundle
from src.policy.au_linkage_depth import build_au_fact_review_bundle_linkage_receipt


def attach_au_fact_review_bundle_linkage_receipt(review_bundle: Mapping[str, Any]) -> dict[str, Any]:
    artifact = deepcopy(dict(review_bundle))
    artifact["linkage_depth_receipt"] = build_au_fact_review_bundle_linkage_receipt(review_bundle)
    return artifact


def build_au_fact_review_bundle_with_linkage_receipt(
    conn,
    *,
    fact_run_id: str,
    semantic_report: Mapping[str, Any],
    source_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    review_bundle = build_au_fact_review_bundle(
        conn,
        fact_run_id=fact_run_id,
        semantic_report=semantic_report,
        source_events=source_events,
    )
    return attach_au_fact_review_bundle_linkage_receipt(review_bundle)


__all__ = [
    "attach_au_fact_review_bundle_linkage_receipt",
    "build_au_fact_review_bundle_with_linkage_receipt",
]
