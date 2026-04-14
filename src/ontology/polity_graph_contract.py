"""Deterministic polity graph contract for jurisdiction-aware follow surfaces."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable


def polity_graph_contract() -> dict[str, str | Iterable[str]]:
    return {
        "scope": "polity jurisdiction graph contract",
        "constraints": [
            "polity nodes describe accurate macro -> sub -> adjudication relationships",
            "edges remain deterministic and traceable via canonical identifiers",
            "language-neutral labels carry provenance but do not promote outside jurisdiction boundaries",
        ],
        "authority_signal": "derived-only macro-jurisdiction ancestry with explicit adjudication context",
        "justification": (
            "Keeps jurisdictional intelligence grounded in a deterministic graph, avoiding "
            "unbounded doctrine branching while enabling consistent follow targeting."
        ),
    }


@dataclass(frozen=True)
class PolityNode:
    node_id: str
    name: str
    level: str
    parent: str | None
    metadata: dict[str, Any]


def build_sample_polity_graph() -> dict[str, PolityNode]:
    nodes = [
        PolityNode(
            node_id="jur:us",
            name="United States",
            level="federal",
            parent=None,
            metadata={"code": "US", "type": "macro"},
        ),
        PolityNode(
            node_id="jur:us:ca",
            name="California",
            level="state",
            parent="jur:us",
            metadata={"code": "CA", "type": "sub"},
        ),
        PolityNode(
            node_id="jur:us:ny",
            name="New York",
            level="state",
            parent="jur:us",
            metadata={"code": "NY", "type": "sub"},
        ),
        PolityNode(
            node_id="jur:eu",
            name="European Union",
            level="macro-region",
            parent=None,
            metadata={"code": "EU", "type": "macro"},
        ),
        PolityNode(
            node_id="jur:eu:fr",
            name="France",
            level="member-state",
            parent="jur:eu",
            metadata={"code": "FR", "type": "member"},
        ),
        PolityNode(
            node_id="jur:au",
            name="Australia",
            level="federal",
            parent=None,
            metadata={"code": "AU", "type": "macro"},
        ),
        PolityNode(
            node_id="jur:au:nsw",
            name="New South Wales",
            level="state",
            parent="jur:au",
            metadata={"code": "NSW", "type": "sub"},
        ),
        PolityNode(
            node_id="jur:gcc",
            name="Gulf Cooperation Council",
            level="regional",
            parent=None,
            metadata={"code": "GCC", "type": "macro"},
        ),
        PolityNode(
            node_id="jur:uae",
            name="United Arab Emirates",
            level="federal",
            parent="jur:gcc",
            metadata={"code": "UAE", "type": "member"},
        ),
        PolityNode(
            node_id="jur:uae:dubai",
            name="Dubai Emirate",
            level="emirate",
            parent="jur:uae",
            metadata={"code": "DXB", "type": "emirate"},
        ),
    ]
    return {node.node_id: node for node in nodes}


def export_polity_graph_nodes() -> dict[str, dict[str, Any]]:
    graph = build_sample_polity_graph()
    return {node_id: asdict(node) for node_id, node in graph.items()}
