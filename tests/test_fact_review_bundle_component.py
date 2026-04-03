from __future__ import annotations

from src.fact_intake.review_bundle import (
    build_abstentions,
    build_bundle_workflow_summary,
    build_event_chronology,
    build_fact_review_bundle_payload,
)


def test_build_event_chronology_orders_by_time_then_semantic_order() -> None:
    chronology = build_event_chronology(
        [
            {
                "event_id": "e2",
                "source_event_ids": ["u2"],
                "event_type": "communication",
                "primary_actor": "Alice",
                "object_text": "Thanks",
                "time_start": None,
                "status": "candidate",
            },
            {
                "event_id": "e1",
                "source_event_ids": ["u1"],
                "event_type": "meeting",
                "primary_actor": "Bob",
                "object_text": "Clinic",
                "time_start": "2026-03-05",
                "status": "captured",
            },
        ],
        semantic_order={"u2": 2, "u1": 1},
    )

    assert [row["event_id"] for row in chronology] == ["e1", "e2"]
    assert chronology[0]["order"] == 1
    assert chronology[1]["order"] == 2


def test_build_abstentions_rolls_up_statement_observation_and_fact_ids() -> None:
    abstentions = build_abstentions(
        {
            "statements": [
                {"statement_id": "s1", "statement_status": "abstained"},
                {"statement_id": "s2", "statement_status": "captured"},
            ],
            "observations": [
                {"observation_id": "o1", "observation_status": "abstained"},
                {"observation_id": "o2", "observation_status": "captured"},
            ],
            "facts": [
                {"fact_id": "f1", "candidate_status": "abstained"},
                {"fact_id": "f2", "candidate_status": "candidate"},
            ],
        }
    )

    assert abstentions["statement_ids"] == ["s1"]
    assert abstentions["observation_ids"] == ["o1"]
    assert abstentions["fact_ids"] == ["f1"]
    assert abstentions["counts"] == {
        "statement_abstentions": 1,
        "observation_abstentions": 1,
        "fact_abstentions": 1,
    }


def test_build_fact_review_bundle_payload_shapes_shared_envelope() -> None:
    bundle = build_fact_review_bundle_payload(
        fact_report={
            "run": {
                "run_id": "factrun:123",
                "source_label": "transcript_semantic:abc",
                "created_at": "2026-03-31T00:00:00Z",
                "workflow_link": {"workflow_kind": "transcript_semantic"},
            },
            "summary": {"event_count": 2},
            "sources": [{"source_id": "src:1"}],
            "excerpts": [{"excerpt_id": "excerpt:1"}],
            "statements": [{"statement_id": "statement:1"}],
            "observations": [{"observation_id": "obs:1"}],
            "events": [{"event_id": "event:1"}],
            "facts": [{"fact_id": "fact:1"}],
        },
        review_summary={
            "chronology_groups": {"dated_events": [{"event_id": "event:1"}]},
            "review_queue": [{"fact_id": "fact:1"}],
            "contested_summary": {"chronology_impacted_count": 1},
            "chronology_summary": {"approximate_event_count": 0},
        },
        semantic_run_id="semantic:1",
        source_documents=[{"sourceDocumentId": "doc:1"}],
        chronology=[
            {
                "order": 1,
                "event_id": "event:1",
                "source_event_ids": ["u1"],
                "event_type": "communication",
                "primary_actor": "Alice",
                "object_text": "Thanks",
                "time_start": "2026-03-31",
                "status": "candidate",
            }
        ],
        abstentions={
            "statement_ids": [],
            "observation_ids": [],
            "fact_ids": [],
            "counts": {
                "statement_abstentions": 0,
                "observation_abstentions": 0,
                "fact_abstentions": 0,
            },
        },
        operator_views={"intake_triage": {"available": True}},
        semantic_context={"summary": {"relation_candidate_count": 1}},
        chronology_summary_extras={"legal_procedural_observation_count": 2},
        workflow_summary={"stage": "decide", "recommended_view": "intake_triage"},
    )

    assert bundle["run"]["semantic_run_id"] == "semantic:1"
    assert bundle["summary"]["source_document_count"] == 1
    assert bundle["chronology_summary"]["bundle_event_count"] == 1
    assert bundle["chronology_summary"]["bundle_dated_event_count"] == 1
    assert bundle["chronology_summary"]["legal_procedural_observation_count"] == 2
    assert bundle["review_queue"][0]["fact_id"] == "fact:1"
    assert bundle["workflow_summary"]["recommended_view"] == "intake_triage"


def test_build_bundle_workflow_summary_prefers_authority_follow() -> None:
    summary = build_bundle_workflow_summary(
        review_summary={
            "summary": {"review_queue_count": 2},
            "contested_summary": {"needs_followup_count": 0},
            "chronology_summary": {"undated_event_count": 0, "no_event_fact_count": 0},
        },
        operator_views={
            "authority_follow": {
                "summary": {"queue_count": 1},
                "queue": [{"item_id": "follow:1"}],
            },
            "intake_triage": {"groups": {"all": [], "missing_actor": [{"fact_id": "fact:1"}]}},
        },
        promotion_gate={"decision": "audit"},
        default_fact_id="fact:1",
    )

    assert summary["stage"] == "follow_up"
    assert summary["recommended_view"] == "authority_follow"
    assert summary["focus_fact_id"] == "fact:1"
    assert summary["promotion_gate"]["decision"] == "audit"
