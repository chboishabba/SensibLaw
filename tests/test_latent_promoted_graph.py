from __future__ import annotations

from pathlib import Path

import jsonschema
import yaml

from src.cross_system_phi import extract_promoted_records_from_report
from src.latent_promoted_graph import build_latent_promoted_graph
from tests.test_cross_system_phi_prototype import _build_au_report, _build_gwb_report


def _load_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.latent_promoted_graph.v1.schema.yaml").read_text(encoding="utf-8"))


def test_latent_promoted_graph_builds_from_real_au_promoted_records(tmp_path: Path) -> None:
    au_report = _build_au_report(tmp_path)
    records = extract_promoted_records_from_report(system_id="au_hca", report=au_report)

    payload = build_latent_promoted_graph(
        system_id="au_hca",
        promoted_basis_ref=f"promoted://au_hca/run/{au_report['run_id']}",
        records=records,
    )

    jsonschema.validate(payload, _load_schema())

    assert payload["payload_version"] == "sl.latent_promoted_graph.v1"
    assert payload["summary"]["fact_node_count"] == len(records)
    assert payload["summary"]["motif_node_count"] >= 1
    assert payload["summary"]["legal_claim_node_count"] >= 1
    assert payload["summary"]["node_type_counts"]["fact"] == len(records)
    assert payload["summary"]["edge_type_counts"]["member_of"] == len(records)
    assert len(payload["record_index"]) == len(records)

    record_index = {row["record_ref"]: row for row in payload["record_index"]}
    node_refs = {row["node_ref"] for row in payload["nodes"]}
    provenance_refs = {row["provenance_ref"] for row in payload["provenance_index"]}

    for record in records:
        indexed = record_index[record["record_ref"]]
        assert indexed["fact_node_ref"] in node_refs
        assert indexed["subject_node_ref"] in node_refs
        assert indexed["object_node_ref"] in node_refs
        assert indexed["document_node_ref"] in node_refs
        assert indexed["authority_node_ref"] in node_refs
        assert indexed["motif_node_refs"]
        assert record["record_ref"] in provenance_refs
        if record.get("rule_type") == "review_relation":
            assert indexed["legal_claim_node_ref"] in node_refs


def test_latent_promoted_graph_builds_for_gwb_with_authority_and_document_nodes(tmp_path: Path) -> None:
    gwb_report = _build_gwb_report(tmp_path)
    records = extract_promoted_records_from_report(system_id="us_exec_judicial", report=gwb_report)

    payload = build_latent_promoted_graph(
        system_id="us_exec_judicial",
        promoted_basis_ref=f"promoted://us_exec_judicial/run/{gwb_report['run_id']}",
        records=records,
    )

    jsonschema.validate(payload, _load_schema())

    node_types = {row["node_type"] for row in payload["nodes"]}
    edge_types = {row["edge_type"] for row in payload["edges"]}

    assert "authority" in node_types
    assert "document" in node_types
    assert {"instantiated_by", "refers_to", "member_of", "applies_to"} <= edge_types


def test_latent_promoted_graph_emits_promoted_legal_claim_edges_for_review_relations(tmp_path: Path) -> None:
    au_report = _build_au_report(tmp_path)
    records = extract_promoted_records_from_report(system_id="au_hca", report=au_report)

    payload = build_latent_promoted_graph(
        system_id="au_hca",
        promoted_basis_ref=f"promoted://au_hca/run/{au_report['run_id']}",
        records=records,
    )

    review_relation_refs = {
        row["record_ref"]
        for row in records
        if row.get("rule_type") == "review_relation"
    }
    claim_nodes = [row for row in payload["nodes"] if row["node_type"] == "legal_claim"]
    claim_edges = [row for row in payload["edges"] if row["edge_type"] in {"grounds_claim", "claim_subject", "claim_object"}]

    assert review_relation_refs
    assert len(claim_nodes) == len(review_relation_refs)
    assert claim_edges
    assert all(
        set(edge["provenance_refs"]) <= review_relation_refs
        for edge in claim_edges
    )
