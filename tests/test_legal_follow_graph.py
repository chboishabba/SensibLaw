from __future__ import annotations

from pathlib import Path

from src.cross_system_phi import extract_promoted_records_from_report
from src.latent_promoted_graph import build_latent_promoted_graph
from src.policy.legal_follow_graph import (
    LEGAL_FOLLOW_GRAPH_VERSION,
    build_au_legal_follow_graph,
    build_au_legal_follow_operator_view,
)
from tests.test_cross_system_phi_prototype import _build_au_report


def _semantic_report() -> dict[str, object]:
    return {
        "authority_receipts": {
            "items": [
                {
                    "ingest_run_id": "ingest:1",
                    "authority_kind": "austlii",
                    "ingest_mode": "known_authority_fetch",
                    "citation": "[1936] HCA 40",
                    "link_status": "linked",
                    "resolved_url": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                    "linked_event_ids": ["ev-1"],
                    "matched_authority_titles": ["House v The King"],
                    "matched_legal_refs": [
                        "case_ref:house_v_the_king",
                        "act_ref:civil_liability_act_2002_nsw",
                    ],
                    "matched_legal_ref_details": [
                        {
                            "canonical_ref": "case_ref:house_v_the_king",
                            "reference_class": "case",
                            "ref_kind": "case_ref",
                            "source_title": "House v The King",
                            "neutral_citation": "[1936] HCA 40",
                        },
                        {
                            "canonical_ref": "act_ref:civil_liability_act_2002_nsw",
                            "reference_class": "supporting_legislation",
                            "ref_kind": "act_ref",
                            "source_title": "Civil Liability Act 2002 (NSW)",
                        },
                    ],
                    "structured_summary": {
                        "detected_neutral_citations": ["[1936] HCA 40"],
                        "detected_neutral_citation_details": [
                            {
                                "raw_text": "[1936] HCA 40",
                                "neutral_citation": "[1936] HCA 40",
                                "court_hint": "HCA",
                                "year_hint": 1936,
                            }
                        ],
                        "selected_paragraph_numbers": [1, 2],
                        "linked_event_sections": ["Appeal"],
                    },
                }
            ],
            "follow_needed_events": [
                {
                    "event_id": "ev-2",
                    "event_section": "Support legislation",
                    "event_text": "The reason turns on the supporting statute and a cited instrument.",
                    "authority_titles": ["Native Title"],
                    "legal_refs": ["act_ref:native_title_new_south_wales_act_1994"],
                    "legal_ref_details": [
                        {
                            "canonical_ref": "act_ref:native_title_new_south_wales_act_1994",
                            "reference_class": "supporting_legislation",
                            "ref_kind": "act_ref",
                            "source_title": "Native Title (New South Wales) Act 1994",
                        }
                    ],
                    "candidate_citations": ["[1992] HCA 23"],
                    "candidate_citation_details": [
                        {
                            "raw_text": "[1992] HCA 23",
                            "neutral_citation": "[1992] HCA 23",
                            "court_hint": "HCA",
                            "year_hint": 1992,
                        }
                    ],
                }
            ],
        }
    }


def _admissibility_report() -> dict[str, object]:
    return {
        "per_event": [
            {
                "event_id": "ev-1",
                "section": "Appeal",
                "text": "The court applied the statute.",
            }
        ],
        "authority_receipts": {"items": [], "follow_needed_events": []},
        "relation_candidates": [
            {
                "candidate_id": "cand-1",
                "event_id": "ev-1",
                "predicate_key": "applied",
                "display_label": "Applied",
                "subject": {
                    "entity_kind": "actor",
                    "canonical_key": "actor:court",
                    "canonical_label": "Court",
                },
                "object": {
                    "entity_kind": "legal_ref",
                    "canonical_key": "legal_ref:native_title_act_1994",
                    "canonical_label": "Native Title Act 1994",
                },
            }
        ],
    }


def _priority_report() -> dict[str, object]:
    return {
        "per_event": [
            {
                "event_id": "ev-audit",
                "section": "Appeal",
                "text": "The court applied the statute.",
            },
            {
                "event_id": "ev-promoted",
                "section": "Appeal",
                "text": "The court followed the statute.",
            },
        ],
        "authority_receipts": {
            "items": [
                {
                    "ingest_run_id": "ingest:1",
                    "authority_kind": "austlii",
                    "citation": "[1936] HCA 40",
                    "link_status": "linked",
                    "resolved_url": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                    "linked_event_ids": ["ev-audit"],
                    "matched_authority_titles": ["House v The King"],
                    "matched_legal_refs": [],
                    "matched_legal_ref_details": [],
                    "structured_summary": {
                        "detected_neutral_citations": ["[1936] HCA 40"],
                        "detected_neutral_citation_details": [
                            {
                                "raw_text": "[1936] HCA 40",
                                "neutral_citation": "[1936] HCA 40",
                                "court_hint": "HCA",
                                "year_hint": 1936,
                            }
                        ],
                        "selected_paragraph_numbers": [1],
                        "linked_event_sections": ["Appeal"],
                    },
                }
            ],
            "follow_needed_events": [],
        },
        "relation_candidates": [
            {
                "candidate_id": "cand-audit",
                "event_id": "ev-audit",
                "predicate_key": "applied",
                "display_label": "Applied",
                "subject": {
                    "entity_kind": "actor",
                    "canonical_key": "actor:court",
                    "canonical_label": "Court",
                },
                "object": {
                    "entity_kind": "legal_ref",
                    "canonical_key": "legal_ref:native_title_act_1994",
                    "canonical_label": "Native Title Act 1994",
                },
            },
            {
                "candidate_id": "cand-promoted",
                "event_id": "ev-promoted",
                "predicate_key": "followed",
                "display_label": "Followed",
                "promotion_status": "promoted_true",
                "canonical_promotion_status": "promoted_true",
                "subject": {
                    "entity_kind": "actor",
                    "canonical_key": "actor:court",
                    "canonical_label": "Court",
                },
                "object": {
                    "entity_kind": "legal_ref",
                    "canonical_key": "legal_ref:native_title_act_1994",
                    "canonical_label": "Native Title Act 1994",
                },
            },
        ],
    }


def test_build_au_legal_follow_graph_is_derived_and_challengeable() -> None:
    graph = build_au_legal_follow_graph(_semantic_report(), source_events=[{"event_id": "ev-1", "section": "Appeal"}])

    assert graph["version"] == LEGAL_FOLLOW_GRAPH_VERSION
    assert graph["derived_only"] is True
    assert graph["challengeable"] is True
    assert graph["pressure"]["kind"] == "pressure_lattice"
    assert graph["pressure"]["version"] == "sl.legal_follow_pressure.v1"
    assert graph["pressure"]["value"] in {"none", "low", "medium", "high", "critical"}
    assert graph["summary"]["event_count"] == 2
    assert graph["summary"]["authority_receipt_count"] == 1
    assert graph["summary"]["node_count"] >= 5
    assert graph["summary"]["edge_count"] >= 4
    assert graph["summary"]["case_ref_count"] >= 1
    assert graph["summary"]["supporting_legislation_count"] >= 1

    kinds = {node["kind"] for node in graph["nodes"]}
    assert {"event", "authority_title", "case_ref", "supporting_legislation", "citation", "authority_receipt"} <= kinds

    edge_kinds = {edge["kind"] for edge in graph["edges"]}
    assert {"mentions_authority_title", "mentions_supporting_legislation", "mentions_citation"} <= edge_kinds
    assert "linked_authority_receipt" in edge_kinds
    assert "supported_by_authority_receipt" in edge_kinds
    assert "resolved_citation" in edge_kinds
    assert "supports_supporting_legislation" in edge_kinds


def test_build_au_legal_follow_graph_keeps_legal_refs_visible_without_truth_or_prediction_claims() -> None:
    graph = build_au_legal_follow_graph(_semantic_report())

    supporting_nodes = [node for node in graph["nodes"] if node["kind"] == "supporting_legislation"]
    case_ref_nodes = [node for node in graph["nodes"] if node["kind"] == "case_ref"]
    assert supporting_nodes
    assert case_ref_nodes
    assert any("civil liability act 2002" in node["label"].lower() for node in supporting_nodes)
    assert any("native title" in node["label"].lower() for node in supporting_nodes)
    assert any("house v the king" in node["label"].lower() for node in case_ref_nodes)

    assert "decision" not in graph
    assert "prediction" not in graph
    assert "risk" not in graph
    assert "verdict" not in graph

    for node in graph["nodes"]:
        assert "prediction" not in node["metadata"]
        assert "risk" not in node["metadata"]
        assert "verdict" not in node["metadata"]


def test_build_au_legal_follow_graph_merges_richer_receipt_and_citation_metadata() -> None:
    graph = build_au_legal_follow_graph(_semantic_report())

    supporting_node = next(
        node for node in graph["nodes"] if node["id"] == "supporting_legislation:act_ref_civil_liability_act_2002_nsw"
    )
    assert supporting_node["metadata"]["reference_class"] == "supporting_legislation"
    assert supporting_node["metadata"]["ref_kind"] == "act_ref"
    assert supporting_node["metadata"]["source_title"] == "Civil Liability Act 2002 (NSW)"
    assert supporting_node["metadata"]["jurisdiction_hint"] == "NSW"
    assert supporting_node["metadata"]["instrument_kind"] == "act"
    assert "supporting_legislation_roles" in supporting_node["metadata"]
    assert "enabling_legislation" in supporting_node["metadata"]["supporting_legislation_roles"]

    citation_node = next(node for node in graph["nodes"] if node["id"] == "citation:1936__hca_40")
    assert citation_node["metadata"]["neutral_citation"] == "[1936] HCA 40"
    assert citation_node["metadata"]["court_hint"] == "HCA"
    assert citation_node["metadata"]["year_hint"] == 1936

    receipt_node = next(node for node in graph["nodes"] if node["kind"] == "authority_receipt")
    assert receipt_node["metadata"]["selected_paragraph_numbers"] == [1, 2]
    assert receipt_node["metadata"]["linked_event_sections"] == ["Appeal"]

    support_edge = next(edge for edge in graph["edges"] if edge["kind"] == "supports_supporting_legislation")
    assert support_edge["metadata"]["reference_class"] == "supporting_legislation"
    assert support_edge["metadata"]["ref_kind"] == "act_ref"
    assert support_edge["metadata"]["jurisdiction_hint"] == "NSW"
    assert support_edge["metadata"]["instrument_kind"] == "act"

    citation_edge = next(edge for edge in graph["edges"] if edge["kind"] == "resolved_citation")
    assert citation_edge["metadata"]["court_hint"] == "HCA"
    assert citation_edge["metadata"]["year_hint"] == 1936


def test_build_au_legal_follow_graph_aggregates_attachment_provenance_on_shared_nodes() -> None:
    graph = build_au_legal_follow_graph(_semantic_report(), source_events=[{"event_id": "ev-1", "section": "Appeal"}])

    title_node = next(node for node in graph["nodes"] if node["id"] == "authority_title:house_v_the_king")
    assert title_node["metadata"]["supporting_receipt_ids"] == ["ingest:1"]

    supporting_node = next(
        node for node in graph["nodes"] if node["id"] == "supporting_legislation:act_ref_civil_liability_act_2002_nsw"
    )
    assert supporting_node["metadata"]["supporting_receipt_ids"] == ["ingest:1"]
    assert supporting_node["metadata"]["supporting_authority_kinds"] == ["austlii"]

    citation_node = next(node for node in graph["nodes"] if node["id"] == "citation:1936__hca_40")
    assert citation_node["metadata"]["supporting_receipt_ids"] == ["ingest:1"]
    assert citation_node["metadata"]["supporting_authority_kinds"] == ["austlii"]

    followup_citation_node = next(node for node in graph["nodes"] if node["id"] == "citation:1992__hca_23")
    assert followup_citation_node["metadata"]["supporting_event_ids"] == ["ev-2"]
    assert followup_citation_node["metadata"]["supporting_event_sections"] == ["Support legislation"]
    assert graph["summary"]["supporting_receipt_count"] >= 1
    assert graph["summary"]["supporting_authority_kind_counts"].get("austlii") >= 1
    assert graph["summary"]["reference_kind_counts"].get("supporting_legislation") >= 1
    assert graph["summary"]["reference_class_counts"].get("supporting_legislation") >= 1
    assert graph["summary"]["ref_kind_counts"].get("act_ref") >= 1
    assert graph["summary"]["jurisdiction_hint_counts"].get("NSW") >= 1
    assert graph["summary"]["instrument_kind_counts"].get("act") >= 1
    assert graph["summary"]["citation_court_hint_counts"].get("HCA") >= 1
    assert graph["summary"]["citation_year_counts"].get("1936") >= 1
    assert graph["summary"]["edge_kind_counts"].get("supports_supporting_legislation") >= 1
    assert graph["summary"]["edge_reference_class_counts"].get("supporting_legislation") >= 1
    assert graph["summary"]["edge_ref_kind_counts"].get("act_ref") >= 1
    assert graph["summary"]["supporting_legislation_role_counts"].get("enabling_legislation") >= 1


def test_operator_view_exposes_parliamentary_control() -> None:
    graph = build_au_legal_follow_graph(_semantic_report())
    view = build_au_legal_follow_operator_view(graph)
    control = view.get("parliamentary_follow_control") or {}
    assert control["score"] > 0.2
    assert "debate" in control["sources"]
    assert view.get("parliamentary_samples")
    assert view["pressure"] == graph["pressure"]
    assert view["summary"]["pressure"] == graph["pressure"]


def test_build_au_legal_follow_graph_supporting_legislation_summary_counts() -> None:
    graph = build_au_legal_follow_graph(_semantic_report())
    summary = graph["summary"]

    assert summary["reference_kind_counts"].get("supporting_legislation") >= 1
    assert summary["reference_class_counts"].get("supporting_legislation") >= 1
    assert summary["instrument_kind_counts"].get("act") >= 1
    assert summary["jurisdiction_hint_counts"].get("NSW") >= 1
    assert summary["edge_kind_counts"].get("supports_supporting_legislation") >= 1
    assert summary["edge_ref_kind_counts"].get("act_ref") >= 1


def test_build_au_legal_follow_graph_derives_uk_follow_target() -> None:
    report = {
        "authority_receipts": {
            "items": [
                {
                    "ingest_run_id": "uk:1",
                    "authority_kind": "bailii",
                    "citation": "1984 UKHL 3",
                    "resolved_url": "https://www.bailii.org/uk/cases/UKHL/1984/3.html",
                    "link_status": "linked",
                    "matched_authority_titles": [],
                    "matched_legal_refs": [],
                    "matched_legal_ref_details": [],
                    "linked_event_ids": [],
                }
            ],
            "follow_needed_events": [],
        }
    }

    graph = build_au_legal_follow_graph(report)
    derived_nodes = [node for node in graph["nodes"] if node["kind"] == "derived_follow_target"]
    assert len(derived_nodes) == 1
    derived_node = derived_nodes[0]
    assert derived_node["label"] == "UK/British legal follow target"
    assert set(derived_node["metadata"]["supporting_node_ids"]) == {
        "authority_receipt:uk_1",
        "citation:1984_ukhl_3",
    }
    assert set(derived_node["metadata"]["supporting_fields"]) == {"label", "resolved_url"}

    edge = next(edge for edge in graph["edges"] if edge["kind"] == "suggests_uk_follow_target")
    assert edge["source"] == "authority_receipt:uk_1"
    assert edge["target"] == derived_node["id"]
    assert set(edge["metadata"]["derived_reason_fields"]) == {"label", "resolved_url"}

    assert graph["summary"]["derived_follow_target_count"] == 1
    assert graph["summary"]["derived_uk_follow_target_supporting_node_count"] == 2
    assert graph["pressure"]["value"] == "high"


def test_build_au_legal_follow_graph_reuses_promoted_legal_claims_from_latent_graph(tmp_path: Path) -> None:
    au_report = _build_au_report(tmp_path)
    records = extract_promoted_records_from_report(system_id="au_hca", report=au_report)
    latent_graph = build_latent_promoted_graph(
        system_id="au_hca",
        promoted_basis_ref=f"promoted://au_hca/run/{au_report['run_id']}",
        records=records,
    )

    graph = build_au_legal_follow_graph(
        {
            "run_id": au_report["run_id"],
            "per_event": au_report["per_event"],
            "authority_receipts": {"items": [], "follow_needed_events": []},
            "relation_candidates": [],
            "promoted_relations": au_report["promoted_relations"],
        },
        latent_promoted_graph=latent_graph,
    )

    promoted_claim_nodes = [
        node for node in graph["nodes"]
        if node["kind"] == "legal_claim"
        and node["metadata"].get("semantic_basis") == "promoted_anchor"
    ]
    assert promoted_claim_nodes
    assert graph["summary"]["legal_claim_count"] == len(promoted_claim_nodes)
    assert all(node["metadata"]["canonical_promotion_status"] == "promoted_true" for node in promoted_claim_nodes)
    assert all(node["metadata"]["promoted_record_ref"] for node in promoted_claim_nodes)
    assert any(edge["kind"] == "states_legal_claim" for edge in graph["edges"])
    claim_edges = [edge for edge in graph["edges"] if edge["kind"].startswith("asserts_")]
    assert claim_edges
    assert all(edge["metadata"]["edge_admissibility"]["version"] == "sl.legal_edge_admissibility.v1" for edge in claim_edges)
    assert all("decision" in edge["metadata"]["edge_admissibility"] for edge in claim_edges)


def test_build_au_legal_follow_graph_summarizes_assert_edge_admissibility() -> None:
    graph = build_au_legal_follow_graph(_admissibility_report())

    assert graph["summary"]["assert_edge_count"] == 1
    assert graph["summary"]["assert_edge_admissibility_counts"] == {"audit": 1}
    assert graph["summary"]["assert_edge_admissibility_review_count"] == 1


def test_build_au_legal_follow_graph_attaches_edge_admissibility_to_supported_relation_candidates() -> None:
    graph = build_au_legal_follow_graph(
        {
            "per_event": [
                {
                    "event_id": "ev-1",
                    "section": "Appeal",
                    "text": "The court applied the statute.",
                }
            ],
            "authority_receipts": {"items": [], "follow_needed_events": []},
            "relation_candidates": [
                {
                    "candidate_id": "cand-1",
                    "event_id": "ev-1",
                    "predicate_key": "applied",
                    "display_label": "Applied",
                    "subject": {
                        "entity_kind": "actor",
                        "canonical_key": "actor:court",
                        "canonical_label": "Court",
                    },
                    "object": {
                        "entity_kind": "legal_ref",
                        "canonical_key": "legal_ref:native_title_act_1994",
                        "canonical_label": "Native Title Act 1994",
                    },
                }
            ],
        }
    )

    claim_edge = next(edge for edge in graph["edges"] if edge["kind"] == "asserts_applied")
    admissibility = claim_edge["metadata"]["edge_admissibility"]

    assert admissibility["version"] == "sl.legal_edge_admissibility.v1"
    assert admissibility["decision"] == "audit"
    assert admissibility["edge"]["relation_kind"] == "applies"
    assert "source_endpoint_audit" in admissibility["reasons"]
    assert admissibility["checks"]["shared_support_linkage_present"] is True


def test_build_au_legal_follow_operator_view_exposes_edge_admissibility_queue_and_details() -> None:
    graph = build_au_legal_follow_graph(_admissibility_report())
    view = build_au_legal_follow_operator_view(graph)

    assert view["summary"]["edge_admissibility_counts"] == {"audit": 1}
    assert view["summary"]["edge_admissibility_review_count"] == 1
    assert len(view["edge_admissibility_queue"]) == 1

    queue_row = view["edge_admissibility_queue"][0]
    assert queue_row["decision"] == "audit"
    assert queue_row["edge_kind"] == "asserts_applied"
    assert "source_endpoint_audit" in queue_row["reasons"]

    legal_claim_packet = next(item for item in view["queue"] if item["subtitle"] == "legal_claim_follow")
    assert any(row["label"] == "Edge admissibility" for row in legal_claim_packet["detail_rows"])
    assert any(row["label"] == "Edge admissibility reasons" for row in legal_claim_packet["detail_rows"])
    assert "edge_admissibility_rows" in legal_claim_packet


def test_build_au_legal_follow_operator_view_prioritizes_legal_claim_packets_by_admissibility_pressure() -> None:
    graph = build_au_legal_follow_graph(_priority_report())
    view = build_au_legal_follow_operator_view(graph)

    assert view["summary"]["priority_band_counts"]["medium"] == 1
    assert view["summary"]["priority_band_counts"]["low"] >= 1
    assert view["summary"]["highest_priority_score"] > 0
    assert view["summary"]["highest_priority_band"] == "medium"

    first = view["queue"][0]
    second = view["queue"][1]
    assert first["subtitle"] == "legal_claim_follow"
    assert second["subtitle"] == "legal_claim_follow"
    assert first["candidate_id"] == "cand-audit"
    assert second["candidate_id"] == "cand-promoted"
    assert first["priority_rank"] == 1
    assert first["priority_score"] > second["priority_score"]
    assert first["priority_band"] == "medium"
    assert second["priority_band"] == "low"
    assert first["priority_reasons"]
    assert first["priority_reason_counts"]["source_endpoint_audit"] >= 1
    assert any(row["label"] == "Priority score" for row in first["detail_rows"])
    assert any(row["label"] == "Priority band" for row in first["detail_rows"])


def test_build_au_legal_follow_operator_view_emits_bounded_follow_queue() -> None:
    report = {
        "authority_receipts": {
            "items": [
                {
                    "ingest_run_id": "uk:1",
                    "authority_kind": "bailii",
                    "citation": "1984 UKHL 3",
                    "resolved_url": "https://www.bailii.org/uk/cases/UKHL/1984/3.html",
                    "link_status": "linked",
                    "matched_authority_titles": [],
                    "matched_legal_refs": [],
                    "matched_legal_ref_details": [],
                    "linked_event_ids": [],
                }
            ],
            "follow_needed_events": [],
        }
    }

    graph = build_au_legal_follow_graph(report)
    view = build_au_legal_follow_operator_view(graph)

    assert view["available"] is True
    assert view["control_plane"]["version"] == "follow.control.v1"
    assert view["control_plane"]["source_family"] == "au_legal_follow"
    assert view["summary"]["queue_count"] == 3
    assert view["summary"]["route_target_counts"]["uk_british_legal_follow"] == 1
    assert view["summary"]["route_target_counts"]["debate_review"] == 2
    queue_item = view["queue"][0]
    assert queue_item["title"] == "UK/British legal follow target"
    assert queue_item["resolution_status"] == "open"
    assert queue_item["route_target"] == "uk_british_legal_follow"
    assert "cross_jurisdiction" in queue_item["chips"]
    assert any(row["label"] == "Supporting nodes" for row in queue_item["detail_rows"])
    debate_items = [item for item in view["queue"] if "debate" in item["chips"]]
    assert len(debate_items) == 2
    assert any(
        row["label"] == "Edge highlights"
        and any(
            token in row["value"]
            for token in (
                "treaty:uk:withdrawal_agreement",
                "law:uk:climate_act",
                "case:uk:appeal:2024:european_union_withdrawal_act",
            )
        )
        for item in debate_items
        for row in item["detail_rows"]
    )
