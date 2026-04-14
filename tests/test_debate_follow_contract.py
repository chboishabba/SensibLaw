from __future__ import annotations

from src.ontology.debate_follow_contract import (
    debate_control_contract,
    build_sample_debate_records,
    export_debate_records,
)


def test_debate_contract_constraints():
    contract = debate_control_contract()
    assert "parliamentary" in contract["scope"]
    constraints = set(contract["constraints"])
    assert any("non-binding" in constraint for constraint in constraints)
    assert contract["authority_signal"].startswith("derived-only")
    assert "structured metadata" in contract["justification"]


def test_sample_debates_reference_instruments():
    debates = build_sample_debate_records()
    assert debates["debate:uk:commons:2023:climate"].chamber == "House of Commons"
    assert "law:uk:climate_act" in debates["debate:uk:commons:2023:climate"].referenced_instruments
    assert "defense_policy" in debates["debate:aus:senate:2022:defense"].influence_tags
    assert "brexit_environment" in debates["debate:uk:commons:2023:climate"].influence_tags
    assert "iraq_policy" in debates["debate:aus:senate:2022:defense"].influence_tags
    uk_edges = debates["debate:uk:commons:2023:climate"].edges
    assert "refers_to:treaty:uk:paris" in uk_edges
    assert "refers_to:treaty:uk:withdrawal_agreement" in uk_edges
    assert any(edge.startswith("influences:case:uk") for edge in uk_edges)
    au_edges = debates["debate:aus:senate:2022:defense"].edges
    assert "refers_to:treaty:aus:us:2001:iraq_coalition_support" in au_edges
    assert "influences:case:aus:federal:2023:iraq_commitment" in au_edges


def test_export_records_serialized():
    exported = export_debate_records()
    assert isinstance(exported["debate:aus:senate:2022:defense"], dict)
    assert exported["debate:uk:commons:2023:climate"]["date"] == "2023-07-12"
    assert "influences:case:uk:appeal:2024:european_union_withdrawal_act" in exported["debate:uk:commons:2023:climate"]["edges"]
