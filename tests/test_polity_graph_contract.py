from __future__ import annotations

from src.ontology.polity_graph_contract import (
    polity_graph_contract,
    build_sample_polity_graph,
    export_polity_graph_nodes,
)


def test_polity_graph_contract_structure():
    contract = polity_graph_contract()
    assert contract["scope"].startswith("polity")
    constraints = list(contract["constraints"])
    assert any("deterministic" in constraint for constraint in constraints)
    assert contract["authority_signal"].startswith("derived-only")
    assert "graph" in contract["justification"]


def test_sample_polity_graph_parents():
    graph = build_sample_polity_graph()
    assert "jur:us" in graph
    assert graph["jur:us:ca"].parent == "jur:us"
    assert graph["jur:uae:dubai"].level == "emirate"
    assert graph["jur:uae"].parent == "jur:gcc"
    assert graph["jur:au:nsw"].metadata["code"] == "NSW"


def test_exported_nodes_are_dicts():
    exported = export_polity_graph_nodes()
    assert isinstance(exported["jur:us"], dict)
    assert exported["jur:uae"]["metadata"]["type"] == "member"
    assert exported["jur:eu:fr"]["parent"] == "jur:eu"
