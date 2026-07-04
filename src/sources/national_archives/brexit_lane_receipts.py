from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from src.policy.brexit_linkage import (
    build_brexit_archive_policy_intent_linkage_receipt,
)
from src.sources.national_archives.brexit_national_archives_lane import (
    build_brexit_national_archives_world_model_report,
)


def attach_brexit_archive_policy_intent_linkage_receipt(report: Mapping[str, Any]) -> dict[str, Any]:
    artifact = deepcopy(dict(report))
    artifact["linkage_depth_receipt"] = build_brexit_archive_policy_intent_linkage_receipt(report)
    return artifact


def build_brexit_national_archives_world_model_report_with_linkage_receipt(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    report = build_brexit_national_archives_world_model_report(records)
    return attach_brexit_archive_policy_intent_linkage_receipt(report)


__all__ = [
    "attach_brexit_archive_policy_intent_linkage_receipt",
    "build_brexit_national_archives_world_model_report_with_linkage_receipt",
]
