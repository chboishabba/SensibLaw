from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.gwb_us_law.semantic import build_gwb_semantic_report
from src.policy.gwb_broader_review_world_model import (
    build_gwb_broader_review_world_model_report,
)
from src.policy.gwb_linkage_depth import build_gwb_broader_review_linkage_receipt
from src.policy.gwb_narrative_linkage import build_gwb_narrative_timeline_linkage_receipt


def attach_gwb_broader_review_linkage_receipt(report: Mapping[str, Any]) -> dict[str, Any]:
    artifact = deepcopy(dict(report))
    artifact["linkage_depth_receipt"] = build_gwb_broader_review_linkage_receipt(report)
    return artifact


def build_gwb_broader_review_world_model_report_with_linkage_receipt(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    report = build_gwb_broader_review_world_model_report(payload)
    return attach_gwb_broader_review_linkage_receipt(report)


def attach_gwb_narrative_timeline_linkage_receipt(report: Mapping[str, Any]) -> dict[str, Any]:
    artifact = deepcopy(dict(report))
    artifact["linkage_depth_receipt"] = build_gwb_narrative_timeline_linkage_receipt(report)
    return artifact


def build_gwb_semantic_report_with_linkage_receipt(conn: Any, *, run_id: str) -> dict[str, Any]:
    report = build_gwb_semantic_report(conn, run_id=run_id)
    return attach_gwb_narrative_timeline_linkage_receipt(report)


__all__ = [
    "attach_gwb_broader_review_linkage_receipt",
    "attach_gwb_narrative_timeline_linkage_receipt",
    "build_gwb_broader_review_world_model_report_with_linkage_receipt",
    "build_gwb_semantic_report_with_linkage_receipt",
]
