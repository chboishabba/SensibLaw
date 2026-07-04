from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.brexit_linkage import build_receipt as _build_receipt
from src.policy.linkage_workflows import attach_receipt as _attach_receipt
from src.policy.linkage_workflows import build_report as _build_with_workflow
from src.sources.national_archives.brexit_national_archives_lane import (
    build_report as _build_report,
    build_world_model as _build_world_model,
    load_records as _load_records,
)


def attach_receipt(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _attach_receipt(artifact, receipt_builder=_build_receipt)


def load_records() -> Sequence[Mapping[str, Any]]:
    return _load_records()


def build_world_model(
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return dict(_build_world_model(records if records is not None else _load_records()))


def build_report(
    records: Sequence[Mapping[str, Any]] | None = None,
    *,
    with_receipt: bool = False,
) -> dict[str, Any]:
    return _build_with_workflow(
        report_builder=_build_report,
        report_args=(records if records is not None else _load_records(),),
        receipt_builder=_build_receipt,
        with_receipt=with_receipt,
    )


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
    "load_records",
]
