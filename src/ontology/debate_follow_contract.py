"""Normalized debate follow/control semantics for parliamentary references."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Mapping, Sequence


def debate_control_contract() -> dict[str, str | Iterable[str]]:
    return {
        "scope": "parliamentary debate follow/control",
        "constraints": [
            "debates reference bills, statutes, or treaties but remain non-binding",
            "control semantics capture competing interpretations without promoting outcomes",
            "edges encode refers_to/influences relationships with treaties, statutes, and cases",
            "links remain deterministic, with explicit identifiers for referenced instruments",
        ],
        "authority_signal": "derived-only debate influence; provenance stays anchored to the debate record",
        "justification": (
            "Keeps debate control lanes advisory while providing structured metadata for operator review."
        ),
    }


@dataclass(frozen=True)
class DebateRecord:
    debate_id: str
    legislature: str
    chamber: str
    date: str
    summary: str
    referenced_instruments: list[str]
    competing_views: list[str]
    influence_tags: list[str]
    edges: list[str]


def build_sample_debate_records() -> dict[str, DebateRecord]:
    debates = [
        DebateRecord(
            debate_id="debate:uk:commons:2023:climate",
            legislature="Parliament of the United Kingdom",
            chamber="House of Commons",
            date="2023-07-12",
            summary="Framed climate policy through the Brexit transition debates on withdrawal agreement obligations.",
            referenced_instruments=[
                "bill:uk:environment:2023",
                "law:uk:climate_act",
                "treaty:uk:withdrawal_agreement",
            ],
            competing_views=["economic_growth vs. emission targets", "national security resilience"],
            influence_tags=["climate_policy", "statutory_amendment", "brexit_environment"],
            edges=[
                "refers_to:treaty:uk:paris",
                "refers_to:law:uk:climate_act",
                "refers_to:treaty:uk:withdrawal_agreement",
                "influences:case:uk:appeal:2024:european_union_withdrawal_act",
            ],
        ),
        DebateRecord(
            debate_id="debate:aus:senate:2022:defense",
            legislature="Parliament of Australia",
            chamber="Senate",
            date="2022-04-05",
            summary="Anchored defense cooperation debates in Iraq mission lessons and US coalition agreements.",
            referenced_instruments=["bill:aus:defense_cooperation", "treaty:aus:us:2001:iraq_coalition_support"],
            competing_views=["sovereignty concerns vs. alliance obligations"],
            influence_tags=["defense_policy", "foreign_relations", "iraq_policy"],
            edges=[
                "refers_to:treaty:aus:us:2001:iraq_coalition_support",
                "refers_to:bill:aus:defense_cooperation",
                "influences:case:aus:federal:2023:iraq_commitment",
            ],
        ),
    ]
    return {record.debate_id: record for record in debates}


def export_debate_records() -> dict[str, dict[str, Any]]:
    graph = build_sample_debate_records()
    return {debate_id: asdict(record) for debate_id, record in graph.items()}
