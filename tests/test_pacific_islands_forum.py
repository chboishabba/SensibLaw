from __future__ import annotations

from src.ontology.pacific_islands_forum import (
    pacific_forum_contract,
    build_pacific_forum_members,
    export_pacific_forum_members,
)


def test_pacific_forum_contract_notes_customary_scope():
    contract = pacific_forum_contract()
    assert "Pacific Islands Forum" in contract["scope"]
    constraints = list(contract["constraints"])
    assert any("customary" in constraint.lower() for constraint in constraints)
    assert "derived-only" in contract["authority_signal"]
    assert "misattributing" in contract["justification"]


def test_member_graph_contains_expected_states():
    members = build_pacific_forum_members()
    assert "pif:fiji" in members
    assert members["pif:png"].capital == "Port Moresby"
    assert "customary" in members["pif:samoa"].customary_sensitivity.lower()
    assert "kastom" in members["pif:vanuatu"].customary_sensitivity.lower()


def test_exported_members_are_dicts_with_notes():
    exported = export_pacific_forum_members()
    assert exported["pif:tonga"]["hybrid_notes"].startswith("Customary")
    assert exported["pif:png"]["customary_sensitivity"].startswith("Strong")
    assert exported["pif:png"]["capital"] == "Port Moresby"
