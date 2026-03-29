from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jsonschema
import yaml

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline
from src.cross_system_phi import build_cross_system_phi_prototype
from src.cross_system_phi_meta import build_default_phi_meta_contract
from src.gwb_us_law.linkage import ensure_gwb_us_law_schema, import_gwb_us_law_seed_payload
from src.gwb_us_law.semantic import build_gwb_semantic_report, ensure_gwb_semantic_schema, run_gwb_semantic_pipeline
from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def _load_schema() -> dict:
    return yaml.safe_load(Path("schemas/sl.cross_system_phi.contract.v1.schema.yaml").read_text(encoding="utf-8"))


def _build_au_report(tmp_path: Path) -> dict:
    db_path = tmp_path / "phi_au.sqlite"
    seed_payload = json.loads((Path("data/ontology/au_semantic_linkage_seed_v1.json")).read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Appeal",
                "text": "The appellant appealed and the matter was heard by the High Court in House v The King.",
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "The plaintiff challenged the Native Title (NSW) Act 1994, but the Court was not separately identified.",
            },
        ],
    }
    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=timeline_payload,
        timeline_path=tmp_path / "wiki_timeline_hca_s942025_aoo.json",
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        import_au_semantic_seed_payload(conn, seed_payload)
        result = run_au_semantic_pipeline(conn)
        return build_au_semantic_report(conn, run_id=result["run_id"])


def _build_gwb_report(tmp_path: Path) -> dict:
    db_path = tmp_path / "phi_gwb.sqlite"
    seed_payload = json.loads((Path("data/ontology/gwb_us_law_linkage_seed_v1.json")).read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_gwb.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 2005, "text": "September 29, 2005"},
                "section": "Confirmations",
                "text": "John Roberts was confirmed by the Senate on September 29, 2005.",
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2006, "text": "October 17, 2006"},
                "section": "Legislation",
                "text": "On October 17, 2006, Bush signed the Military Commissions Act of 2006 into law.",
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 2008, "text": "July 31, 2008"},
                "section": "Litigation",
                "text": "On July 31, 2008, a United States district court judge ruled that the Military Commissions Act of 2006 was unconstitutional.",
            },
        ],
    }
    persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=timeline_payload,
        timeline_path=tmp_path / "wiki_timeline_gwb.json",
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        ensure_gwb_us_law_schema(conn)
        ensure_gwb_semantic_schema(conn)
        import_gwb_us_law_seed_payload(conn, seed_payload)
        result = run_gwb_semantic_pipeline(conn)
        return build_gwb_semantic_report(conn, run_id=result["run_id"])


def test_cross_system_phi_prototype_builds_from_real_promoted_reports(tmp_path: Path) -> None:
    au_report = _build_au_report(tmp_path)
    gwb_report = _build_gwb_report(tmp_path)

    payload = build_cross_system_phi_prototype(
        motif_family="review_and_authority_relations",
        source_system_id="au_hca",
        source_authority_scope="Promoted AU appellate/review relations from the bounded High Court fixture.",
        source_report=au_report,
        target_system_id="us_exec_judicial",
        target_authority_scope="Promoted US governance/review relations from the bounded GWB fixture.",
        target_report=gwb_report,
    )

    jsonschema.validate(payload, _load_schema())

    assert payload["payload_version"] == "sl.cross_system_phi.contract.v1"
    assert payload["meta_contract_ref"] == "schema://sl.cross_system_phi_meta.v1"
    assert "bounded v1 transport contract" in payload["versioning_note"]
    assert "future Phi v2 semantics" in payload["versioning_note"]
    assert len(payload["latent_graphs"]) == 2
    assert all(row["graph_version"] == "sl.latent_promoted_graph.v1" for row in payload["latent_graphs"])
    assert payload["provenance_rule"]["rule_id"] == "sl.phi.provenance_dual_anchor.v1"
    assert payload["provenance_rule"]["source_anchor_required"] is True
    assert payload["provenance_rule"]["target_anchor_required"] is True
    assert payload["mismatch_report"]["workflow"]["workflow_id"] == "sl.phi_mismatch_review.v1"
    assert payload["mismatch_report"]["workflow"]["default_status"] == "open"

    statuses = {row["status"] for row in payload["mappings"]}
    assert "partial" in statuses
    assert "incompatible" in statuses

    partial_mapping = next(row for row in payload["mappings"] if row["status"] == "partial")
    incompatible_mapping = next(row for row in payload["mappings"] if row["status"] == "incompatible")
    assert partial_mapping["target_ref"] is not None
    assert incompatible_mapping["target_ref"] is not None
    assert partial_mapping["meta_validation"]["allowed"] is True
    assert incompatible_mapping["meta_validation"]["allowed"] is True
    assert partial_mapping["meta_validation"]["witness"]["authority_alignment"]["relation"] in {"exact", "analogue"}
    assert partial_mapping["mapping_explanation"]["meta_summary"]["authority_relation"] in {"exact", "analogue"}
    assert partial_mapping["mapping_explanation"]["witness"]["type_alignment"]["relation"] == "exact"
    assert partial_mapping["mapping_explanation"]["latent_graph_refs"]["source_fact_node_ref"]
    assert partial_mapping["mapping_explanation"]["latent_graph_refs"]["target_fact_node_ref"]
    assert partial_mapping["mapping_explanation"]["latent_graph_refs"]["source_motif_ref"]
    assert partial_mapping["mapping_explanation"]["latent_graph_refs"]["target_motif_ref"]
    assert incompatible_mapping["mapping_explanation"]["meta_summary"]["constraint_status"] in {"compatible", "conditional"}

    provenance_index = {row["provenance_ref"]: row for row in payload["provenance_index"]}
    for mapping in payload["mappings"]:
        for provenance_ref in mapping["provenance_refs"]:
            assert provenance_ref in provenance_index
            provenance_row = provenance_index[provenance_ref]
            assert provenance_row["source_char_end"] > provenance_row["source_char_start"]
            assert provenance_row["event_text"]

    for diagnostic in payload["mismatch_report"]["diagnostics"]:
        assert diagnostic["status"] == "open"
        assert len(diagnostic["provenance_refs"]) == 2
        systems = {provenance_index[ref]["system_id"] for ref in diagnostic["provenance_refs"]}
        assert systems == {"au_hca", "us_exec_judicial"}

    assert partial_mapping["mismatch_refs"]
    assert incompatible_mapping["mismatch_refs"]
    assert incompatible_mapping["mapping_id"] in payload["mismatch_report"]["incompatible_mapping_ids"]
    assert payload["meta_validation_report"]["blocked_pairs"]
    blocked_pair = payload["meta_validation_report"]["blocked_pairs"][0]
    assert blocked_pair["meta_validation"]["allowed"] is False
    assert "authority_relation_incompatible" in blocked_pair["meta_validation"]["violations"]
    assert blocked_pair["source_ref"] in payload["meta_validation_report"]["blocked_source_refs"]
    assert blocked_pair["meta_validation"]["witness"]["authority_alignment"]["relation"] == "incompatible"


def test_cross_system_phi_prototype_uses_default_meta_contract_shape() -> None:
    contract = build_default_phi_meta_contract(left_system="au_hca", right_system="us_exec_judicial")
    assert contract["version"] == "sl.cross_system_phi_meta.v1"
    assert contract["thresholds"]["min_total_score"] == 0.72


def test_cross_system_phi_minimal_example_still_validates_under_extended_schema() -> None:
    payload = json.loads(Path("examples/cross_system_phi_minimal.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load_schema())
