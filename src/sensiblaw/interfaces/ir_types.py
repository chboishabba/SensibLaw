from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionMode(str, Enum):
    BOTTOM = "bottom"
    AMBIENT = "ambient"
    STATEMENT = "statement"
    INTERROGATIVE = "interrogative"
    IMPERATIVE = "imperative"
    DIRECTED_REQUEST = "directed_request"


@dataclass(frozen=True, slots=True)
class QueryNode:
    node_id: str
    text: str
    span_start: int
    span_end: int
    kind: str
    token_indices: tuple[int, ...] = ()
    features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryEdge:
    src_id: str
    dst_id: str
    kind: str
    evidence_span: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class QueryTree:
    text: str
    nodes: tuple[QueryNode, ...]
    edges: tuple[QueryEdge, ...]
    root_ids: tuple[str, ...]
    receipts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InteractionProjectionReceipt:
    interaction_mode: InteractionMode
    supporting_node_ids: tuple[str, ...] = ()
    supporting_signal_ids: tuple[str, ...] = ()
    projection_version: str = "interaction_projection_v1"

