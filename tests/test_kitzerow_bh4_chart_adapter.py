"""Kitzerow chart crosswalk: proof of native generic carrier reuse.

A published creator chart *identifier* is not itself an independently tested
physiological event. The full proprietary network cannot be inferred from the
limited published chart. No public ontology, SLR store or biological state is
mutated.
"""
from copy import deepcopy

import pytest

from src.policy.kitzerow_bh4_chart_adapter import build_world
from src.policy.linkage_depth import (
    audit_linkage_depth_case,
    build_expected_layer_contract,
    build_linkage_depth_case,
)

PAGE = "https://www.researchgate.net/publication/377218425_BH4FolateCobalaminHomocysteine_Pathway"


def _input():
    chart = {
        "schema": "dashi.kitzerow-primary-chart-rhea-index.v1",
        "creator": "Kimberly Kitzerow", "publication_page": PAGE,
        "declared_publication_month": "2024-01",
        "observed_full_text_upload_date": "2025-08-08",
        "whole_proprietary_network_reconstructed": False,
        "primary_claims_paid_by_source_index": False,
        "same_compartment_flux_paid": False,
        "license_declared": "CC BY-NC-ND 4.0",
        "rhea_identifiers": [
            {"rhea_id": "RHEA:21708", "web_text_line": 91},
            {"rhea_id": "RHEA:21080", "web_text_line": 104},
        ],
    }
    matrix = {
        "schema": "dashi.bh4-stoichiometric-matrix.v1",
        "reaction_index": ["RHEA:21080", "RHEA:99999"],
    }
    return chart, matrix


def test_native_chart_bridge_and_review_visibility():
    c, m = _input()
    result = build_world(c, m)
    world = result["world_model"]
    assert world["schema_version"] == "sl.candidate_world_model.v0_1"
    assert world["summary"]["identifier_overlap"] == ["RHEA:21080"]
    assert world["summary"]["chart_observed_only"] == ["RHEA:21708"]
    assert world["summary"]["finite_panel_only"] == ["RHEA:99999"]
    assert world["summary"]["denominator_for_whole_creator_network"] is None
    assert len(world["external_bridge_candidates"]) == 2
    assert all(x["candidate_status"] == "review_required"
               and x["promotion_authority"] is False
               and x["attachment_kind"] == "related_concept"
               for x in world["external_bridge_candidates"])
    assert all(x["outcome"] == "abstain" for x in world["external_pressure_results"])
    assert world["external_graph_views"][0]["coverage_state"] == "incomplete"
    assert result["review_projection"]["projection_kind"] == "review_surface"
    assert len(result["review_projection"]["payload"]["external_bridge_candidates"]) == 2
    assert result["source_authority"].startswith("creator-authored")
    assert world["metadata"]["live_ontology_writes"] is False

    link = result["linkage_fragment"]
    assert "kitzerow:chart:377218425" in link["expected_anchor_ids"]
    assert "kitzerow:bh4:review-tranche" in link["expected_terminal_ids"]
    assert any(edge["kind"] == "external_bridge_projection" for edge in link["edges"])
    contract = build_expected_layer_contract(
        contract_id="kitzerow-rhea-native-bridge",
        domain="source-anchored-biochemistry-review",
        anchor_kind="source_anchor",
        expected_layers=["source_anchor", "domain_candidate", "external_candidate", "review_surface", "tranche_anchor"],
        required_bridges=[["source_anchor", "domain_candidate"],
                          ["domain_candidate", "external_candidate"],
                          ["external_candidate", "review_surface"],
                          ["review_surface", "tranche_anchor"]],
        terminal_anchor="tranche_anchor",
        required_authority_boundaries=["external_candidate"],
    )
    case = build_linkage_depth_case(
        case_id="kitzerow-rhea-source-native",
        case_kind="biology_external_graph",
        contract_id=contract["contract_id"],
        contract=contract,
        nodes=link["nodes"], edges=link["edges"],
        expected_anchor_ids=link["expected_anchor_ids"],
        expected_terminal_ids=link["expected_terminal_ids"],
    )
    audit = audit_linkage_depth_case(case)
    assert audit["linkage_depth_status"] in ("complete", "partial", "shallow")


@pytest.mark.parametrize("mutation", [
    lambda c, m: c.update(whole_proprietary_network_reconstructed=True),
    lambda c, m: c.update(primary_claims_paid_by_source_index=True),
    lambda c, m: c.update(same_compartment_flux_paid=True),
    lambda c, m: c["rhea_identifiers"].append(c["rhea_identifiers"][0]),
    lambda c, m: c["rhea_identifiers"][0].update(web_text_line=0),
    lambda c, m: m.update(reaction_index=["CHEBI:1"]),
])
def test_fail_closed(mutation):
    c, m = _input()
    mutation(c, m)
    with pytest.raises(ValueError):
        build_world(c, m)


def test_reordering_keeps_deterministic_model():
    c, m = _input()
    rev = deepcopy(c)
    rev["rhea_identifiers"].reverse()
    assert build_world(c, m) == build_world(rev, m)
