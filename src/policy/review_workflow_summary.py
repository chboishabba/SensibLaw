from __future__ import annotations

from .decision_surface import build_decision_surface


def build_count_priority_workflow_summary(**kwargs: object) -> dict[str, object]:
    return build_decision_surface(**kwargs)


__all__ = ["build_count_priority_workflow_summary"]
