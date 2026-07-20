from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping, Sequence


def attach_receipt(
    artifact: Mapping[str, Any],
    *,
    receipt_builder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    payload = deepcopy(dict(artifact))
    payload["linkage_depth_receipt"] = dict(receipt_builder(artifact))
    return payload


def build_report(
    *,
    report_builder: Callable[..., Mapping[str, Any]],
    report_args: Sequence[Any] = (),
    report_kwargs: Mapping[str, Any] | None = None,
    receipt_builder: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    report = dict(report_builder(*report_args, **dict(report_kwargs or {})))
    if not with_receipt or receipt_builder is None:
        return report
    return attach_receipt(report, receipt_builder=receipt_builder)


def load_fixture(
    *,
    fixture_builder: Callable[..., Mapping[str, Any]],
    fixture_args: Sequence[Any] = (),
    fixture_kwargs: Mapping[str, Any] | None = None,
    receipt_builder: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    with_receipt: bool = False,
) -> dict[str, Any]:
    artifact = dict(fixture_builder(*fixture_args, **dict(fixture_kwargs or {})))
    if not with_receipt or receipt_builder is None:
        return artifact
    return attach_receipt(artifact, receipt_builder=receipt_builder)


__all__ = [
    "attach_receipt",
    "build_report",
    "load_fixture",
]
