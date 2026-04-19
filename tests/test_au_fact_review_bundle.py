from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
from pathlib import Path

import jsonschema
import yaml

from src.au_semantic.linkage import ensure_au_semantic_schema, import_au_semantic_seed_payload
from src.au_semantic.semantic import build_au_semantic_report, run_au_semantic_pipeline
from src.fact_intake import (
    AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION,
    EVENT_ASSEMBLER_VERSION,
    FACT_REVIEW_BUNDLE_VERSION,
    build_au_fact_review_bundle,
    build_au_fact_review_bundle_world_model_report,
    build_fact_intake_payload_from_au_semantic_report,
    persist_fact_intake_payload,
    persist_authority_ingest_receipt,
    record_fact_workflow_link,
)
from src.fact_intake.review_bundle import build_bundle_workflow_summary
from src.models.action_policy import ACTION_POLICY_SCHEMA_VERSION
from src.models.convergence import CONVERGENCE_SCHEMA_VERSION
from src.models.conflict import CONFLICT_SCHEMA_VERSION
from src.models.nat_claim import NAT_CLAIM_SCHEMA_VERSION
from src.models.review_claim_record import REVIEW_CLAIM_RECORD_SCHEMA_VERSION
from src.models.temporal import TEMPORAL_SCHEMA_VERSION
from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized, persist_wiki_timeline_aoo_run
import src.fact_intake.au_review_bundle as au_review_bundle
from src.policy.legal_follow_graph import (
    build_au_legal_follow_graph,
    build_au_legal_follow_operator_view,
)


def _seed_au_fixture_db(db_path: Path) -> str:
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "au_semantic_linkage_seed_v1.json"
    seed_payload = json.loads(seed_path.read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(db_path.parent / "wiki_timeline_hca_s942025_aoo.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 1992, "text": "1992"},
                "section": "Native title",
                "text": "In Mabo [No 2], the High Court rejected terra nullius and recognized native title against the Commonwealth of Australia.",
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2003, "text": "2003"},
                "section": "Judicial review",
                "text": "In Plaintiff S157/2002 v Commonwealth the High Court challenged the Migration Act privative clause as part of judicial review.",
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 1936, "text": "1936"},
                "section": "Criminal appeal",
                "text": "In House v The King the appellant brought an appeal and the matter was heard by the High Court.",
            },
        ],
    }
    persisted = persist_wiki_timeline_aoo_run(
        db_path=db_path,
        out_payload=timeline_payload,
        timeline_path=db_path.parent / "wiki_timeline_hca_s942025_aoo.json",
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        import_au_semantic_seed_payload(conn, seed_payload)
    return persisted.run_id


def _prepare_au_fact_review_bundle_fixture(tmp_path: Path):
    db_path = tmp_path / "itir.sqlite"
    timeline_run_id = _seed_au_fixture_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        ensure_au_semantic_schema(conn)
        result = run_au_semantic_pipeline(conn)
        persist_authority_ingest_receipt(
            conn,
            {
                "version": "authority.ingest.v1",
                "authority_kind": "austlii",
                "ingest_mode": "known_authority_fetch",
                "citation": "[1936] HCA 40",
                "selection_reason": "by_citation:[1936] HCA 40",
                "resolved_url": "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/cth/HCA/1936/40.html",
                "content_type": "text/html",
                "content_length": 120,
                "content_sha256": hashlib.sha256(b"house-v-the-king").hexdigest(),
                "body_preview_text": "House v The King judgment excerpt discussing the High Court appeal.",
                "segments": [
                    {
                        "segment_kind": "paragraph",
                        "paragraph_number": 1,
                        "segment_text": "House v The King concerned an appeal heard by the High Court.",
                    }
                ],
            },
        )
        semantic_report = build_au_semantic_report(conn, run_id=result["run_id"])
        source_payload = load_run_payload_from_normalized(conn, timeline_run_id) or {}
        source_events = source_payload.get("events") if isinstance(source_payload.get("events"), list) else []
        payload = build_fact_intake_payload_from_au_semantic_report(semantic_report, timeline_events=source_events)
        persist_summary = persist_fact_intake_payload(conn, payload)
        record_fact_workflow_link(
            conn,
            workflow_kind="au_semantic",
            workflow_run_id=result["run_id"],
            fact_run_id=payload["run"]["run_id"],
            source_label=payload["run"]["source_label"],
        )
        bundle = build_au_fact_review_bundle(
            conn,
            fact_run_id=payload["run"]["run_id"],
            semantic_report=semantic_report,
            source_events=source_events,
        )
    return bundle, payload, persist_summary, semantic_report


def test_au_semantic_report_adapts_into_fact_review_bundle(tmp_path: Path) -> None:
    bundle, payload, persist_summary, semantic_report = _prepare_au_fact_review_bundle_fixture(tmp_path)

    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact.review.bundle.v1.schema.yaml"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(bundle, schema)

    assert payload["run"]["run_id"].startswith("factrun:")
    assert payload["run"]["source_label"] == f"au_semantic:{semantic_report['run_id']}"
    assert persist_summary["statement_count"] == 3
    assert persist_summary["fact_count"] == 3
    assert persist_summary["observation_count"] >= 6
    assert persist_summary["event_count"] >= 2

    observation_predicates = {row["predicate_key"] for row in bundle["observations"]}
    assert {"actor", "performed_action", "acted_on", "event_date"} <= observation_predicates
    assert {"appealed", "challenged", "heard_by"} & observation_predicates

    appeal_like_event = next(
        event for event in bundle["events"] if event["event_type"] in {"appealed", "challenged", "heard by", "decided by", "applied"}
    )
    assert appeal_like_event["assembler_version"] == EVENT_ASSEMBLER_VERSION
    assert appeal_like_event["status"] == "candidate"
    assert appeal_like_event["source_event_ids"]
    assert {row["role"] for row in appeal_like_event["evidence"]} >= {"event_type", "primary_actor"}

    assert bundle["version"] == FACT_REVIEW_BUNDLE_VERSION
    assert bundle["run"]["semantic_run_id"] == semantic_report["run_id"]
    assert bundle["run"]["workflow_link"]["workflow_kind"] == "au_semantic"
    assert bundle["summary"]["source_document_count"] == 1
    assert bundle["summary"]["event_count"] >= 2
    assert len(bundle["review_queue"]) == 3
    assert any(row["legal_procedural_predicates"] for row in bundle["review_queue"])
    assert any(row["has_legal_procedural_observations"] for row in bundle["review_queue"])
    assert bundle["chronology_groups"]["dated_events"] or bundle["chronology_groups"]["approximate_events"]
    assert bundle["chronology_summary"]["approximate_event_count"] >= 1
    assert bundle["workflow_summary"]["stage"] in {"inspect", "decide", "record", "follow_up"}
    assert bundle["workflow_summary"]["recommended_view"] in {
        "intake_triage",
        "chronology_prep",
        "contested_items",
        "authority_follow",
        "legal_follow_graph",
        "professional_handoff",
    }
    assert bundle["workflow_summary"]["counts"]["review_queue_count"] >= 0
    assert "procedural_posture" in bundle["operator_views"]
    assert "authority_follow" in bundle["operator_views"]
    assert bundle["abstentions"]["counts"]["observation_abstentions"] >= 0
    assert bundle["semantic_context"]["summary"]["relation_candidate_count"] >= 1
    assert "au_linkage" in bundle["semantic_context"]
    assert bundle["semantic_context"]["authority_receipts"]["summary"]["authority_receipt_count"] >= 1
    assert bundle["semantic_context"]["authority_receipts"]["summary"]["linked_receipt_count"] >= 1
    assert bundle["semantic_context"]["authority_receipts"]["items"][0]["structured_summary"]["selected_paragraph_numbers"] == [1]
    assert bundle["operator_views"]["authority_follow"]["available"] is True
    assert bundle["operator_views"]["authority_follow"]["control_plane"]["version"] == "follow.control.v1"
    assert bundle["operator_views"]["authority_follow"]["control_plane"]["source_family"] == "au_authority"
    assert bundle["operator_views"]["authority_follow"]["summary"]["authority_receipt_count"] >= 1
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["legal_ref_class_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["ref_kind_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["citation_court_hint_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["citation_year_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["jurisdiction_hint_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["instrument_kind_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["route_target_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["resolution_status_counts"], dict)
    assert isinstance(bundle["operator_views"]["authority_follow"]["summary"]["priority_band_counts"], dict)
    assert bundle["operator_views"]["authority_follow"]["summary"]["highest_priority_score"] >= 0
    assert bundle["operator_views"]["authority_follow"]["summary"]["highest_authority_yield"] in {
        "high",
        "medium",
        "low",
    }
    assert isinstance(bundle["operator_views"]["authority_follow"]["queue"], list)
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["title"]
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["resolution_status"] == "open"
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["priority_rank"] == 1
    assert "priority_score" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert bundle["operator_views"]["authority_follow"]["queue"][0]["authority_yield"] in {"high", "medium", "low"}
    assert any(row["label"] == "Reference classes" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Reference kinds" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Authority yield" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Citation courts" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Citation years" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Jurisdictions" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert any(row["label"] == "Instrument kinds" for row in bundle["operator_views"]["authority_follow"]["queue"][0]["detail_rows"])
    assert "legal_ref_details" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "candidate_citation_details" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "jurisdiction_hint_counts" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "instrument_kind_counts" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "ref_kind_counts" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "citation_court_hint_counts" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert "citation_year_counts" in bundle["operator_views"]["authority_follow"]["queue"][0]
    assert bundle["operator_views"]["legal_follow_graph"]["available"] is True
    assert bundle["workflow_summary"]["recommended_view"] == "legal_follow_graph"
    assert bundle["workflow_summary"]["promotion_gate"]["decision"] in {"promote", "audit", "abstain"}
    assert bundle["operator_views"]["legal_follow_graph"]["control_plane"]["version"] == "follow.control.v1"
    assert bundle["operator_views"]["legal_follow_graph"]["control_plane"]["source_family"] == "au_legal_follow"
    assert bundle["operator_views"]["legal_follow_graph"]["summary"]["authority_receipt_count"] >= 1
    assert bundle["operator_views"]["legal_follow_graph"]["summary"]["supporting_receipt_count"] >= 1
    assert bundle["operator_views"]["legal_follow_graph"]["summary"]["supporting_authority_kind_counts"].get("austlii") >= 1
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["jurisdiction_hint_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["instrument_kind_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["reference_class_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["ref_kind_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["citation_court_hint_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["citation_year_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["edge_kind_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["supporting_legislation_role_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["route_target_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["resolution_status_counts"], dict)
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["summary"]["edge_admissibility_counts"], dict)
    assert bundle["operator_views"]["legal_follow_graph"]["summary"]["assert_edge_admissibility_count"] >= 1
    assert bundle["operator_views"]["legal_follow_graph"]["pressure"]["kind"] == "pressure_lattice"
    assert bundle["operator_views"]["legal_follow_graph"]["summary"]["pressure"] == bundle["operator_views"]["legal_follow_graph"]["pressure"]
    assert isinstance(bundle["operator_views"]["legal_follow_graph"]["queue"], list)
    assert bundle["semantic_context"]["workflow"]["workflow_kind"] == "au_semantic"
    assert {"appealed", "challenged", "heard_by"} & set(bundle["semantic_context"]["legal_procedural_summary"]["predicates"])
    assert bundle["semantic_context"]["legal_follow_graph"]["summary"]["node_count"] >= 1
    assert bundle["semantic_context"]["legal_follow_graph"]["summary"]["edge_count"] >= 1
    assert isinstance(bundle["semantic_context"]["legal_follow_graph"]["summary"]["edge_admissibility_counts"], dict)
    assert bundle["semantic_context"]["legal_follow_graph"]["summary"]["assert_edge_admissibility_count"] >= 1
    assert bundle["semantic_context"]["legal_follow_graph"]["pressure"]["kind"] == "pressure_lattice"
    assert any(node["kind"] == "authority_receipt" for node in bundle["semantic_context"]["legal_follow_graph"]["nodes"])
    assert any(edge["kind"] == "linked_authority_receipt" for edge in bundle["semantic_context"]["legal_follow_graph"]["edges"])
    assert bundle["compiler_contract"]["lane"] == "au"
    assert bundle["compiler_contract"] == bundle["semantic_context"]["compiler_contract"]
    assert bundle["promotion_gate"]["product_ref"] == "au_fact_review_bundle"
    assert bundle["promotion_gate"] == bundle["semantic_context"]["promotion_gate"]
    assert len(bundle["review_claim_records"]) == len(bundle["review_queue"])
    first_review_claim = bundle["review_claim_records"][0]
    assert first_review_claim["schema_version"] == REVIEW_CLAIM_RECORD_SCHEMA_VERSION
    assert first_review_claim["lane"] == "au"
    assert first_review_claim["source_family"] == "au_fact_review_bundle"
    assert first_review_claim["state"] == "review_claim"
    assert first_review_claim["state_basis"] == "review_bundle"
    assert first_review_claim["evidence_status"] == "review_only"
    normalized_artifact = bundle["semantic_context"]["suite_normalized_artifact"]
    assert normalized_artifact["legal_follow_pressure"] == bundle["semantic_context"]["legal_follow_graph"]["pressure"]
    reasoner_input_artifact = bundle["semantic_context"]["reasoner_input_artifact"]
    assert reasoner_input_artifact["normalized_artifact"]["legal_follow_pressure"] == normalized_artifact["legal_follow_pressure"]


def test_build_bundle_workflow_summary_prefers_legal_follow_when_admissibility_pressure_dominates() -> None:
    summary = build_bundle_workflow_summary(
        review_summary={
            "summary": {"review_queue_count": 0},
            "chronology_summary": {"undated_event_count": 0, "no_event_fact_count": 0},
            "contested_summary": {"needs_followup_count": 0},
        },
        operator_views={
            "authority_follow": {
                "summary": {"queue_count": 1},
                "queue": [{"fact_id": "authority:1"}],
            },
            "legal_follow_graph": {
                "summary": {
                    "queue_count": 2,
                    "edge_admissibility_counts": {"audit": 2, "promote": 0, "abstain": 1},
                },
                "queue": [{"edge_id": "edge:1"}, {"edge_id": "edge:2"}],
            },
        },
        promotion_gate={"decision": "promote"},
        default_fact_id="fact:1",
    )

    assert summary["recommended_view"] == "legal_follow_graph"
    assert summary["stage"] == "follow_up"
    assert summary["counts"]["legal_follow_queue_count"] == 2
    assert summary["counts"]["legal_follow_review_pressure"] == 3
    assert summary["counts"]["legal_follow_promote_count"] == 0


def test_build_bundle_workflow_summary_keeps_authority_follow_when_legal_follow_does_not_dominate() -> None:
    summary = build_bundle_workflow_summary(
        review_summary={
            "summary": {"review_queue_count": 0},
            "chronology_summary": {"undated_event_count": 0, "no_event_fact_count": 0},
            "contested_summary": {"needs_followup_count": 0},
        },
        operator_views={
            "authority_follow": {
                "summary": {"queue_count": 1},
                "queue": [{"fact_id": "authority:1"}],
            },
            "legal_follow_graph": {
                "summary": {
                    "queue_count": 1,
                    "edge_admissibility_counts": {"promote": 3, "audit": 1},
                },
                "queue": [{"edge_id": "edge:1"}],
            },
        },
        promotion_gate={"decision": "promote"},
        default_fact_id="fact:1",
    )

    assert summary["recommended_view"] == "authority_follow"
    assert summary["stage"] == "follow_up"


def test_au_fact_review_bundle_world_model_report_rebinds_bundle_into_shared_substrate(
    tmp_path: Path,
) -> None:
    bundle, _, _, _ = _prepare_au_fact_review_bundle_fixture(tmp_path)

    report = build_au_fact_review_bundle_world_model_report(bundle)

    assert report["schema_version"] == AU_FACT_REVIEW_BUNDLE_WORLD_MODEL_SCHEMA_VERSION
    assert report["claim_schema_version"] == NAT_CLAIM_SCHEMA_VERSION
    assert report["convergence_schema_version"] == CONVERGENCE_SCHEMA_VERSION
    assert report["temporal_schema_version"] == TEMPORAL_SCHEMA_VERSION
    assert report["conflict_schema_version"] == CONFLICT_SCHEMA_VERSION
    assert report["action_policy_schema_version"] == ACTION_POLICY_SCHEMA_VERSION
    assert report["run_id"] == bundle["run"]["fact_run_id"]
    assert report["semantic_run_id"] == bundle["run"]["semantic_run_id"]
    assert report["summary"]["claim_count"] == len(bundle["review_queue"])
    assert report["summary"]["must_review_count"] == len(bundle["review_queue"])
    first_claim = report["claims"][0]
    first_queue_row = bundle["review_queue"][0]
    assert first_claim["claim_id"] == first_queue_row["fact_id"]
    assert first_claim["status"] == "REVIEW_ONLY"
    assert first_claim["nat_claim"]["state_basis"] == "review_bundle"
    assert first_claim["convergence"]["convergence_state"] == "NORMALIZED"
    assert first_claim["conflict_set"]["conflict_type"] == "none"
    assert first_claim["action_policy"]["actionability"] == "must_review"


def test_au_authority_follow_queue_supporting_legislation_counts(tmp_path: Path) -> None:
    bundle, _, _, _ = _prepare_au_fact_review_bundle_fixture(tmp_path)
    queue_item = bundle["operator_views"]["authority_follow"]["queue"][0]
    detail_rows = {row["label"]: row["value"] for row in queue_item["detail_rows"]}

    assert queue_item["priority_score"] >= 1
    assert queue_item["priority_rank"] == 1
    assert queue_item["authority_yield"] in {"high", "medium", "low"}
    assert queue_item["jurisdiction_hint_counts"]
    assert sum(queue_item["jurisdiction_hint_counts"].values()) >= 1
    instrument_counts = queue_item["instrument_kind_counts"]
    if instrument_counts:
        assert sum(instrument_counts.values()) >= 1


def test_au_legal_follow_graph_projects_native_title_relations_into_claim_queue() -> None:
    semantic_report = {
        "relation_candidates": [
            {
                "candidate_id": 101,
                "event_id": "ev-native-title",
                "predicate_key": "distinguished",
                "display_label": "distinguished",
                "promotion_status": "promoted",
                "confidence_tier": "medium",
                "canonical_promotion_status": "promoted_true",
                "canonical_promotion_basis": "structural",
                "semantic_basis": "structural",
                "subject": {
                    "entity_kind": "legal_ref",
                    "canonical_key": "legal_ref:mabo_v_queensland_no_2",
                    "canonical_label": "Mabo v Queensland (No 2)",
                },
                "object": {
                    "entity_kind": "legal_ref",
                    "canonical_key": "legal_ref:terra_nullius_doctrine",
                    "canonical_label": "terra nullius doctrine",
                },
            }
        ]
    }
    source_events = [
        {
            "event_id": "ev-native-title",
            "section": "Native title",
            "text": "Mabo distinguished terra nullius and reshaped native title doctrine.",
        }
    ]

    graph = build_au_legal_follow_graph(semantic_report, source_events=source_events)
    operator_view = build_au_legal_follow_operator_view(graph)

    assert graph["summary"]["legal_claim_count"] == 1
    assert graph["summary"]["legal_claim_predicate_counts"]["distinguished"] == 1
    assert any(node["kind"] == "legal_claim" for node in graph["nodes"])
    assert any(edge["kind"] == "states_legal_claim" for edge in graph["edges"])
    assert any(edge["kind"] == "asserts_distinguished" for edge in graph["edges"])
    assert operator_view["summary"]["queue_count"] >= 1
    legal_claim_queue = next(
        row for row in operator_view["queue"] if row["conjecture_kind"] == "legal_claim_follow"
    )
    assert legal_claim_queue["route_target"] == "au_native_title_follow"
    assert "native_title" in legal_claim_queue["chips"]
    assert legal_claim_queue["predicate_key"] == "distinguished"


def test_au_bundle_uses_shared_review_bundle_component() -> None:
    source = inspect.getsource(au_review_bundle.build_au_fact_review_bundle)
    assert "build_event_chronology(" in source
    assert "build_abstentions(" in source
    assert "build_fact_review_bundle_payload(" in source


def test_au_payload_uses_shared_payload_builder() -> None:
    source = inspect.getsource(au_review_bundle.build_fact_intake_payload_from_au_semantic_report)
    assert "build_fact_intake_run(" in source
    assert "build_source_rows(" in source
    assert "ensure_event_source_row(" in source
    assert "build_excerpt_row(" in source
    assert "build_statement_row(" in source
    assert "build_fact_candidate_row(" in source
    assert "build_fact_intake_payload(" in source


def test_au_payload_uses_shared_observation_projection_path() -> None:
    source = inspect.getsource(au_review_bundle.build_fact_intake_payload_from_au_semantic_report)
    assert "build_role_observation(" in source
    assert "build_relation_observation(" in source


def test_au_payload_uses_shared_projection_helpers() -> None:
    source = inspect.getsource(au_review_bundle.build_fact_intake_payload_from_au_semantic_report)
    assert "fact_status_for_statement(" in source
    assert "observation_status_from_relation(" in source
