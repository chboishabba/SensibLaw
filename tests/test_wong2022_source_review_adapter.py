"""Regression for source-bounded DOI/CID ontology review projection."""

from src.policy.wong2022_source_review_adapter import (
    DLA_CHEBI_REF,
    DLA_PUBCHEM_REF,
    DOI,
    build_wong_2022_candidate_world,
)


def test_wong_2022_world_reuses_native_world_model_and_graph_bridge():
    world = build_wong_2022_candidate_world()
    assert world["schema_version"] == "sl.candidate_world_model.v0_1"
    assert world["model_status"] == "candidate"
    assert world["metadata"]["paper_doi"] == DOI
    assert world["metadata"]["source_artifact_sha256"] is None
    assert world["metadata"]["source_digests_verified"] is False
    assert world["metadata"]["public_ontology_mutation_allowed"] is False
    assert world["metadata"]["clinical_authority"] is False

    graph, = world["external_graph_views"]
    assert graph["coverage_state"] == "incomplete"
    assert graph["candidate_only"] is True
    assert graph["complete_closure"] is False
    assert graph["artifact_revision"] == "version-of-record:2022-02-07"
    assert graph["support_authority"] is False
    assert graph["promotion_authority"] is False
    assert len(graph["unresolved_coverage"]) == 3


def test_wong_2022_compound_cross_refs_are_review_required_not_identity():
    world = build_wong_2022_candidate_world()
    refs = world["external_bridge_candidates"]
    assert len(refs) == 2
    assert {r["external_ref"] for r in refs} == {
        DLA_PUBCHEM_REF, DLA_CHEBI_REF
    }
    assert {r["attachment_kind"] for r in refs} == {"authority_reference"}
    assert {r["candidate_status"] for r in refs} == {"review_required"}
    for row in refs:
        assert row["identity_authority"] is False
        assert row["promotion_authority"] is False
        assert row["residuals"]
    entity, = world["entities"]
    assert entity["metadata"]["sample_registry_identity_certified"] is False
    assert entity["metadata"]["same_entity_as_lysergic_acid_diethylamide"] is False


def test_wong_2022_measurements_remain_author_reports_not_scale_predictions():
    world = build_wong_2022_candidate_world()
    claims = {r["node_id"]: r for r in world["claims"]}
    assert len(claims) == 4
    assert claims["wong2022:claim:one-litre-titre"]["metadata"]["reported_text"] == "1.7 mg/L"
    assert claims["wong2022:claim:four-litre-titre"]["metadata"]["reported_text"] == "1.4 mg/L"
    for claim in claims.values():
        assert claim["status"] == "candidate"
        assert claim["metadata"]["observation_role"] == "primary_author_report"
        assert claim["metadata"]["scientific_truth_authority"] is False
        assert claim["metadata"]["commercial_scale_authority"] is False
        assert claim["metadata"]["clinical_authority"] is False

    pressure, = world["external_pressure_results"]
    assert pressure["outcome"] == "abstain"
    assert pressure["mutation_authority"] is False
    assert pressure["promotion_authority"] is False


def test_wong_2022_output_is_stable_and_read_only():
    first = build_wong_2022_candidate_world()
    second = build_wong_2022_candidate_world()
    assert first == second
    assert first["external_bridge_decisions"] == []
    assert first["relations"] == []
    assert first["metadata"]["source_data_sha256"] is None


def test_wong_2022_cli_exports_stable_candidate_json():
    import json
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root / "scripts/export_wong2022_source_review.py")]
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data == build_wong_2022_candidate_world()
    assert data["metadata"]["public_ontology_mutation_allowed"] is False
    assert data["external_bridge_decisions"] == []
