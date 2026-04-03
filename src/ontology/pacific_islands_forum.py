"""Normalized scaffold for Pacific Islands Forum regional normative surface."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable


def pacific_forum_contract() -> dict[str, str | Iterable[str]]:
    return {
        "scope": "Pacific Islands Forum normative surface",
        "constraints": [
            "members expressed as canonical member-state nodes; forum-level norms remain non-authoritative without national ratification",
            "customary or hybrid law sensitivity described explicitly via separate field descriptors",
            "edges reflect member relationships and forum governance bodies rather than domestic authority hierarchies",
        ],
        "authority_signal": "derived-only regional forum normative metadata; no promotion of forum law without domestic ratification",
        "justification": (
            "Keeps PIF treated as a regional cooperation scaffold so downstream follow lanes can reference membership without misattributing binding authority."
        ),
    }


@dataclass(frozen=True)
class PacificForumMember:
    member_id: str
    name: str
    capital: str
    customary_sensitivity: str
    hybrid_notes: str


def build_pacific_forum_members() -> dict[str, PacificForumMember]:
    members = [
        PacificForumMember(
            member_id="pif:fiji",
            name="Fiji",
            capital="Suva",
            customary_sensitivity="Customary land and village governance retains primacy over general statutes.",
            hybrid_notes="Constitutional instrument blends British common law with indigenous customary land tenure; forum engagement references both.",
        ),
        PacificForumMember(
            member_id="pif:png",
            name="Papua New Guinea",
            capital="Port Moresby",
            customary_sensitivity="Strong customary clan-based legal systems persist outside statutory courts.",
            hybrid_notes="National judiciary explicitly defers to custom via the underlying Constitution; forum notes highlight hybrid dispute resolution.",
        ),
        PacificForumMember(
            member_id="pif:samoa",
            name="Samoa",
            capital="Apia",
            customary_sensitivity="Faʻa Samoa (customary order) shapes family and land disputes before statutory intervention.",
            hybrid_notes="Legislative acts acknowledge matai (chiefly) roles; forum references mark customary interplay.",
        ),
        PacificForumMember(
            member_id="pif:tonga",
            name="Tonga",
            capital="Nukuʻalofa",
            customary_sensitivity="Monarchical and chiefly structures overlay the statutory judiciary.",
            hybrid_notes="Customary overlay flagged for noble privileges and land tenure; forum metadata keeps note separate.",
        ),
        PacificForumMember(
            member_id="pif:vanuatu",
            name="Vanuatu",
            capital="Port Vila",
            customary_sensitivity="Customary 'kastom' directives operate alongside French-English hybrid statutes.",
            hybrid_notes="Constitution allows laws that codify kastom; forum references carefully keep statutory/custom notes distinct.",
        ),
    ]
    return {member.member_id: member for member in members}


def export_pacific_forum_members() -> dict[str, dict[str, Any]]:
    graph = build_pacific_forum_members()
    return {member_id: asdict(member) for member_id, member in graph.items()}
