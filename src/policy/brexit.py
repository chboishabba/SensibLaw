from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.sources.national_archives.brexit_national_archives_lane import (
    load_records as _load_records,
)
from src.policy.world_model_runtime import (
    attach_receipt as _attach_receipt,
    build_world_model as _build_world_model_from_input,
    project_report as _project_report,
)


def attach_receipt(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return _attach_receipt(artifact)


def load_records() -> Sequence[Mapping[str, Any]]:
    return _load_records()


def build_world_model(
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return dict(_build_world_model_from_input(records if records is not None else _load_records()))


def build_report(
    records: Sequence[Mapping[str, Any]] | None = None,
    *,
    with_receipt: bool = False,
) -> dict[str, Any]:
    report = _project_report(build_world_model(records if records is not None else _load_records()))
    if not with_receipt:
        return report
    return _attach_receipt(report)


__all__ = [
    "attach_receipt",
    "build_report",
    "build_world_model",
    "load_records",
]
