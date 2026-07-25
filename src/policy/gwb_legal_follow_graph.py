"""Deprecated GWB follow-graph compatibility wrapper.

Canonical follow state is relational and PostgreSQL-derived.  Historical public
function names remain as detached presentation adapters only; no lane-specific
semantic graph is constructed or accepted.
"""

from __future__ import annotations

from typing import Any, Mapping
import warnings

from src.policy.follow_projection_compat import (
    project_gwb_follow_surface,
    reject_nested_follow_graph_semantic_input,
)
from src.storage.postgres.follow_projection_store import FollowProjectionQueryResult

GWB_LEGAL_FOLLOW_GRAPH_VERSION = "gwb.follow.presentation.v2"


def _require_relational_result(value: object) -> FollowProjectionQueryResult:
    if isinstance(value, FollowProjectionQueryResult):
        return value
    if isinstance(value, Mapping):
        reject_nested_follow_graph_semantic_input(value)
    raise TypeError(
        "GWB follow projection requires FollowProjectionQueryResult from PostgreSQL"
    )


def build_gwb_legal_follow_graph(
    source: FollowProjectionQueryResult,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    if args or kwargs:
        warnings.warn(
            "lane-specific follow construction arguments are deprecated and ignored",
            DeprecationWarning,
            stacklevel=2,
        )
    return project_gwb_follow_surface(_require_relational_result(source))


def build_gwb_legal_follow_operator_view(
    source: FollowProjectionQueryResult,
) -> dict[str, Any]:
    return project_gwb_follow_surface(_require_relational_result(source))


__all__ = [
    "GWB_LEGAL_FOLLOW_GRAPH_VERSION",
    "build_gwb_legal_follow_graph",
    "build_gwb_legal_follow_operator_view",
]
