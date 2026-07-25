"""Deprecated AU follow-graph compatibility wrapper.

Canonical follow state is persisted and queried through the generic PostgreSQL
follow projection.  This module keeps historical import names for presentation
callers only; it cannot construct semantic edges or accept a nested graph bundle.
"""

from __future__ import annotations

from typing import Any, Mapping
import warnings

from src.policy.follow_projection_compat import (
    project_au_follow_surface,
    reject_nested_follow_graph_semantic_input,
)
from src.storage.postgres.follow_projection_store import FollowProjectionQueryResult

LEGAL_FOLLOW_GRAPH_VERSION = "au.follow.presentation.v2"
FOLLOW_CONTROL_PLANE_VERSION = "follow.control.v1"
LEGAL_FOLLOW_PRESSURE_VERSION = "sl.legal_follow_pressure.v2"


def _require_relational_result(value: object) -> FollowProjectionQueryResult:
    if isinstance(value, FollowProjectionQueryResult):
        return value
    if isinstance(value, Mapping):
        reject_nested_follow_graph_semantic_input(value)
    raise TypeError(
        "AU follow projection requires FollowProjectionQueryResult from PostgreSQL"
    )


def build_au_legal_follow_graph(
    source: FollowProjectionQueryResult,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return detached presentation data from a relational query result.

    The historical name is retained for bounded compatibility. No graph is built.
    """
    if args or kwargs:
        warnings.warn(
            "lane-specific follow construction arguments are deprecated and ignored",
            DeprecationWarning,
            stacklevel=2,
        )
    return project_au_follow_surface(_require_relational_result(source))


def build_au_legal_follow_operator_view(
    source: FollowProjectionQueryResult,
) -> dict[str, Any]:
    return project_au_follow_surface(_require_relational_result(source))


def build_legal_follow_graph(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return build_au_legal_follow_graph(*args, **kwargs)


__all__ = [
    "FOLLOW_CONTROL_PLANE_VERSION",
    "LEGAL_FOLLOW_GRAPH_VERSION",
    "LEGAL_FOLLOW_PRESSURE_VERSION",
    "build_au_legal_follow_graph",
    "build_au_legal_follow_operator_view",
    "build_legal_follow_graph",
]
