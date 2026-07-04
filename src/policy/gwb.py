from __future__ import annotations

from typing import Any, Mapping

from src.gwb_us_law.semantic import build_gwb_semantic_report as _build_semantic_report
from src.policy.gwb_broader_review_world_model import (
    build_gwb_broader_review_world_model_report as _build_broader_review_report,
)
from src.policy.gwb_linkage_depth import build_receipt as _build_broader_review_receipt
from src.policy.gwb_narrative_linkage import build_receipt as _build_narrative_receipt
from src.policy.linkage_workflows import attach_receipt as _attach_receipt
from src.policy.linkage_workflows import build_report as _build_report


def attach_receipt(artifact: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    builders = {
        "broader_review": _build_broader_review_receipt,
        "semantic": _build_narrative_receipt,
        "narrative_timeline": _build_narrative_receipt,
    }
    try:
        receipt_builder = builders[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported gwb receipt kind: {kind}") from exc
    return _attach_receipt(artifact, receipt_builder=receipt_builder)


def build_report(payload: Mapping[str, Any], *, with_receipt: bool = False) -> dict[str, Any]:
    return _build_report(
        report_builder=_build_broader_review_report,
        report_args=(payload,),
        receipt_builder=_build_broader_review_receipt,
        with_receipt=with_receipt,
    )


def build_semantic_report(conn: Any, *, run_id: str, with_receipt: bool = False) -> dict[str, Any]:
    return _build_report(
        report_builder=_build_semantic_report,
        report_kwargs={"conn": conn, "run_id": run_id},
        receipt_builder=_build_narrative_receipt,
        with_receipt=with_receipt,
    )


__all__ = [
    "attach_receipt",
    "build_report",
    "build_semantic_report",
]
