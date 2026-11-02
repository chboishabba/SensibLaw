"""Native Rhea/ChEBI extension remains a candidate external graph."""
from copy import deepcopy
import pytest

from src.policy.kitzerow_bh4_chart_adapter import build_world

SOURCE = "https://www.researchgate.net/publication/377218425_BH4FolateCobalaminHomocysteine_Pathway"


def fixture():
    chart = {
        "schema": "dashi.kitzerow-primary-chart-rhea-index.v1",
        "creator": "Kimberly Kitzerow",
        "publication_page": SOURCE,
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
    ids = sorted(r["rhea_id"] for r in chart["rhea_identifiers"])
    receipt = {
        "schema": "dashi.rhea-chebi-bh4-source-chart.v1",
        "creator": chart["creator"],
        "source_chart_publication": SOURCE,
        "source_chart_pdf_sha256_verified": False,
        "whole_creator_network_complete": False,
        "source_chart_index_sha256": "1" * 64,
        "rhea_release_reference": "Rhea source revision fixture",
        "source_rhea_ids_requested": ids,
        "rhea_rows_acquired": 2,
        "rhea_rows_failed": 0,
        "complete_reaction_identity_acquisition": True,
        "reactions": [
            {"rhea_id": rid, "raw_sha256": "2" * 64,
             "participant_sparql_response_sha256": "3" * 64,
             "formula_charge_ready": True,
             "participants": [
                 {"chebi_id": "CHEBI:15378", "side": "substrate", "coefficient": 1},
                 {"chebi_id": "CHEBI:15377", "side": "product", "coefficient": 1},
             ]}
            for rid in ids
        ],
        "errors": [],
    }
    return chart, matrix, receipt


def test_native_curator_attachment():
    chart, matrix, receipt = fixture()
    result = build_world(chart, matrix, creator_reactions=receipt)
    world = result["world_model"]
    assert len(world["external_graph_views"]) == 2
    assert world["external_graph_views"][1]["coverage_state"] == "incomplete"
    assert world["summary"]["creator_curated_Rhea_rows"] == 2
    assert world["summary"]["creator_curated_Rhea_errors"] == 0
    assert len(world["external_bridge_candidates"]) == 6
    assert sum(row["bridge_namespace"] == "chebi" for row in world["external_bridge_candidates"]) == 4
    assert all(row["promotion_authority"] is False
               and row["candidate_status"] == "review_required"
               for row in world["external_bridge_candidates"])
    assert all(row["outcome"] == "abstain" for row in world["external_pressure_results"])
    assert result == build_world(chart, matrix, creator_reactions=receipt)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(source_rhea_ids_requested=["RHEA:21708"]),
    lambda p: p["reactions"][0].update(raw_sha256="placeholder"),
    lambda p: p["reactions"][0]["participants"][0].update(coefficient=0),
    lambda p: p.update(whole_creator_network_complete=True),
    lambda p: p.update(rhea_release_reference=""),
    lambda p: p["errors"].append({"rhea_id": p["reactions"][0]["rhea_id"], "error": "duplicate"}),
])
def test_rhea_curator_fail_closed(mutate):
    chart, matrix, receipt = fixture()
    mutate(receipt)
    with pytest.raises(ValueError):
        build_world(chart, matrix, creator_reactions=receipt)


def test_partial_curator_retrieval_is_not_negative_biology():
    chart, matrix, receipt = fixture()
    failed = receipt["reactions"].pop(0)
    receipt["rhea_rows_acquired"] = 1
    receipt["errors"] = [{"rhea_id": failed["rhea_id"], "error": "source unavailable"}]
    receipt["rhea_rows_failed"] = 1
    receipt["complete_reaction_identity_acquisition"] = False
    result = build_world(chart, matrix, creator_reactions=receipt)
    world = result["world_model"]
    assert world["summary"]["creator_curated_Rhea_rows"] == 1
    assert world["summary"]["creator_curated_Rhea_errors"] == 1
    assert world["external_graph_views"][1]["coverage_state"] == "incomplete"
