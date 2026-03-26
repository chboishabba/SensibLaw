from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gwb_us_law.semantic import (
    ensure_mission_plan_seed,
    ensure_gwb_semantic_schema,
    list_semantic_review_submissions,
    load_mission_actual_mapping_current,
    load_mission_plan,
    submit_semantic_review_submission,
    upsert_mission_actual_mapping,
)
from src.reporting.structure_report import TextUnit
from scripts.transcript_semantic import build_transcript_semantic_cli_payload
from src.transcript_semantic.semantic import build_transcript_semantic_report, run_transcript_semantic_pipeline


def test_transcript_semantic_pipeline_persists_speakers_and_candidate_reply_relations() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "hearing-1", "transcript_file", "Q: Where were you?"),
        TextUnit("u2", "hearing-1", "transcript_file", "A: At home."),
        TextUnit("u3", "hearing-1", "transcript_file", "[5/3/26 8:52 pm] Alice: Thanks."),
    ]
    result = run_transcript_semantic_pipeline(
        conn,
        units,
        known_participants_by_source={"hearing-1": ["counsel", "witness"]},
        run_id="transcript-fixture-v1",
    )
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    assert result["relation_candidate_count"] >= 1
    assert result["promoted_relation_count"] == 0
    entity_keys = {row["entity"]["canonical_key"] for row in report["per_entity"]}
    assert any(key.endswith(":counsel") for key in entity_keys)
    assert any(key.endswith(":witness") for key in entity_keys)
    assert any(key.endswith(":alice") for key in entity_keys)
    event_roles = {row["event_id"]: row["event_roles"] for row in report["per_event"]}
    assert any(role["role_kind"] == "speaker" for role in event_roles["u1"])
    candidate_predicates = {row["predicate_key"] for row in report["candidate_only_relations"]}
    assert "replied_to" in candidate_predicates
    replied_row = next(row for row in report["candidate_only_relations"] if row["predicate_key"] == "replied_to")
    assert replied_row["confidence_tier"] == "low"
    replied_receipts = {(receipt["kind"], receipt["value"]) for receipt in replied_row["receipts"]}
    assert ("rule_type", "conversational_relation") in replied_receipts
    assert ("promotion_status", "candidate") in replied_receipts
    assert replied_row["semantic_candidate"]["schema_version"] == "relation.semantic_candidate.v1"
    assert replied_row["semantic_candidate"]["candidate_kind"] == "semantic_relation"
    assert replied_row["semantic_basis"] == "structural"
    assert replied_row["canonical_promotion_status"] == "abstained"
    assert replied_row["canonical_promotion_basis"] == "structural"
    assert replied_row["canonical_promotion_reason"] == "relation_candidate_not_promoted"

    alice_entity = conn.execute(
        """
        SELECT entity_id, shared_actor_id
        FROM semantic_entities
        WHERE canonical_key = ?
        """,
        ("actor:transcript:hearing_1:alice",),
    ).fetchone()
    assert alice_entity is not None
    assert alice_entity["shared_actor_id"] is not None
    alice_aliases = {
        row["alias_text"]
        for row in conn.execute(
            "SELECT alias_text FROM actor_aliases WHERE actor_id = ?",
            (int(alice_entity["shared_actor_id"]),),
        ).fetchall()
    }
    assert "Alice" in alice_aliases
    replied_policy = conn.execute(
        """
        SELECT rule_type_key, min_confidence, required_evidence_count
        FROM semantic_promotion_policies
        WHERE predicate_key = 'replied_to'
        """
    ).fetchone()
    assert replied_policy is not None
    assert replied_policy["rule_type_key"] == "conversational_relation"
    assert replied_policy["min_confidence"] == "high"
    assert replied_policy["required_evidence_count"] == 3
    assert report["text_debug"]["unavailableReason"] is not None


def test_transcript_semantic_cli_payload_reports_progress() -> None:
    updates: list[tuple[str, dict[str, object]]] = []

    payload = build_transcript_semantic_cli_payload(
        db_path=":memory:",
        run_id="",
        transcript_files=[],
        cmd="summary",
        progress_callback=lambda stage, details: updates.append((stage, details)),
    )

    stages = [stage for stage, _ in updates]
    assert stages[0] == "load_units_started"
    assert "demo_units_used" in stages
    assert "semantic_pipeline_started" in stages
    assert "summary_build_finished" in stages
    assert stages[-1] == "build_finished"
    assert "family_counts" in payload


def test_transcript_semantic_pipeline_abstains_on_timing_only_and_role_only_sources() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "src1", "transcript_file", "[00:00:00,030 -> 00:00:21,970] Thanks."),
        TextUnit("u2", "src1", "chat_test_db", "User: run the tests"),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v2")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    unresolved = {(row["surface_text"], row["resolution_rule"]) for row in report["unresolved_mentions"]}
    assert ("[00:00:00,030 -> 00:00:21,970] Thanks.", "transcript_timing_only_v1") in unresolved
    assert ("user", "role_label_not_person_actor_v1") in unresolved
    assert result["promoted_relation_count"] == 0
    assert not report["promoted_relations"]


def test_transcript_semantic_pipeline_extracts_general_freeform_entities_without_legalizing_text() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit(
            "u1",
            "journal-1",
            "text_file",
            "Picasso met Alice in Paris and was sad that day because he couldn't have his croissant.",
        )
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v3")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    entity_keys = {row["entity"]["canonical_key"] for row in report["per_entity"]}
    assert any(key.endswith(":picasso") for key in entity_keys)
    assert any(key.endswith(":alice") for key in entity_keys)
    assert any(key.endswith(":paris") for key in entity_keys)
    assert any(key.endswith(":croissant") for key in entity_keys)
    event_roles = report["per_event"][0]["event_roles"]
    role_kinds = {row["role_kind"] for row in event_roles}
    assert "subject" in role_kinds
    assert "mentioned_entity" in role_kinds
    assert "theme" in role_kinds
    candidate_predicates = {row["predicate_key"] for row in report["candidate_only_relations"]}
    assert "felt_state" in candidate_predicates
    felt_state_row = next(row for row in report["candidate_only_relations"] if row["predicate_key"] == "felt_state")
    assert felt_state_row["confidence_tier"] == "low"
    all_predicates = {row["predicate_key"] for row in report["relation_candidates"]}
    assert all_predicates <= {"felt_state", "replied_to"}
    assert result["promoted_relation_count"] == 0


def test_transcript_semantic_pipeline_abstains_on_obvious_titlecase_noise() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "journal-2", "text_file", "Thanks for coming."),
        TextUnit("u2", "journal-2", "text_file", "Today was strange."),
        TextUnit("u3", "journal-2", "chat_test_db", "User: keep going"),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v4")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    entity_keys = {row["entity"]["canonical_key"] for row in report["per_entity"]}
    assert not any(key.endswith(":thanks") for key in entity_keys)
    assert not any(key.endswith(":today") for key in entity_keys)
    assert not any(key.endswith(":user") for key in entity_keys)
    unresolved = {(row["surface_text"], row["resolution_rule"]) for row in report["unresolved_mentions"]}
    assert ("user", "role_label_not_person_actor_v1") in unresolved
    assert result["promoted_relation_count"] == 0


def test_transcript_semantic_pipeline_keeps_multi_token_names_and_place_context() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "journal-3", "text_file", "Mary Jane met Bob in Brisbane."),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v5")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    entity_keys = {row["entity"]["canonical_key"] for row in report["per_entity"]}
    assert any(key.endswith(":mary_jane") for key in entity_keys)
    assert any(key.endswith(":bob") for key in entity_keys)
    assert any(key.endswith(":brisbane") for key in entity_keys)
    role_kinds = {row["role_kind"] for row in report["per_event"][0]["event_roles"]}
    assert "subject" in role_kinds
    assert "mentioned_entity" in role_kinds
    assert result["promoted_relation_count"] == 0


def test_transcript_semantic_pipeline_extracts_explicit_social_relations_as_candidate_only() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "journal-4", "text_file", "Mary Jane is Bob's sister."),
        TextUnit("u2", "journal-4", "text_file", "Alice and Carol are friends."),
        TextUnit("u3", "journal-4", "text_file", "Tom is the father of Jane."),
        TextUnit("u4", "journal-4", "text_file", "Alice is the guardian of Carol."),
        TextUnit("u5", "journal-4", "text_file", "Mary cared for Bob."),
        TextUnit("u6", "journal-4", "text_file", "Alice looks after Carol."),
        TextUnit("u7", "journal-4", "text_file", "Mary is responsible for Bob."),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v6")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    candidate_predicates = {row["predicate_key"] for row in report["candidate_only_relations"]}
    assert {"sibling_of", "friend_of", "parent_of", "guardian_of", "caregiver_of"} <= candidate_predicates
    assert result["promoted_relation_count"] == 0
    assert all(row["semantic_candidate"]["candidate_kind"] == "semantic_relation" for row in report["relation_candidates"])

    sibling_row = next(row for row in report["candidate_only_relations"] if row["predicate_key"] == "sibling_of")
    sibling_receipts = {(receipt["kind"], receipt["value"]) for receipt in sibling_row["receipts"]}
    assert ("rule_type", "social_relation") in sibling_receipts
    assert ("promotion_status", "candidate") in sibling_receipts
    assert ("cue_surface", "sister") in sibling_receipts

    event_roles = {row["event_id"]: row["event_roles"] for row in report["per_event"]}
    u1_roles = {row["role_kind"] for row in event_roles["u1"]}
    u2_roles = {row["role_kind"] for row in event_roles["u2"]}
    u3_roles = {row["role_kind"] for row in event_roles["u3"]}
    u4_roles = {row["role_kind"] for row in event_roles["u4"]}
    u5_roles = {row["role_kind"] for row in event_roles["u5"]}
    u6_roles = {row["role_kind"] for row in event_roles["u6"]}
    u7_roles = {row["role_kind"] for row in event_roles["u7"]}
    assert "related_person" in u1_roles
    assert "related_person" in u2_roles
    assert "related_person" in u3_roles
    assert "related_person" in u4_roles
    assert "related_person" in u5_roles
    assert "related_person" in u6_roles
    assert "related_person" in u7_roles

    guardian_row = next(row for row in report["candidate_only_relations"] if row["predicate_key"] == "guardian_of")
    care_row = next(row for row in report["candidate_only_relations"] if row["predicate_key"] == "caregiver_of")
    guardian_receipts = {(receipt["kind"], receipt["value"]) for receipt in guardian_row["receipts"]}
    care_receipts = {(receipt["kind"], receipt["value"]) for receipt in care_row["receipts"]}
    assert ("cue_surface", "guardian") in guardian_receipts
    assert ("cue_surface", "cared_for") in care_receipts
    assert any(value in {"looks_after", "cared_for"} for kind, value in care_receipts if kind == "cue_surface")
    social_debug = next(
        relation
        for event in report["text_debug"]["events"]
        for relation in event["relations"]
        if relation["predicateKey"] == "guardian_of"
    )
    assert social_debug["family"] == "social"


def test_transcript_semantic_report_persists_mission_observer_and_review_submissions_in_db() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("demo-chat-2", "demo-chat-1", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
        TextUnit("demo-chat-3", "demo-chat-1", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-db-review-v1")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    mission_run = conn.execute("SELECT run_id, source FROM mission_runs WHERE run_id = ?", (result["run_id"],)).fetchone()
    assert mission_run is not None
    assert mission_run["source"] == "transcript"
    assert report["mission_observer"]["summary"]["mission_count"] >= 1
    assert conn.execute("SELECT COUNT(*) FROM mission_nodes WHERE run_id = ?", (result["run_id"],)).fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM mission_observer_overlays WHERE run_id = ?", (result["run_id"],)).fetchone()[0] >= 1

    payload = {
        "proposed_predicate_key": "guardian_of",
        "replacement_label": "guardian of",
    }
    evidence = [{"event_id": "demo-chat-3", "ref_kind": "followup_message"}]
    submit_semantic_review_submission(
        conn,
        submission_id="corr:transcript:1",
        source="transcript",
        run_id=str(result["run_id"]),
        corpus_label="Transcript / freeform",
        event_id="demo-chat-3",
        relation_id=None,
        anchor_key="anchor:demo-chat-3:0",
        action_kind="false_positive",
        proposed_payload=payload,
        evidence_refs=evidence,
        operator_provenance={"source": "pytest", "actor": "tester"},
        note="fixture correction",
        created_at="2026-03-08T00:00:00Z",
    )
    rows = list_semantic_review_submissions(conn, source="transcript", run_id=str(result["run_id"]))
    assert len(rows) == 1
    assert rows[0]["action_kind"] == "false_positive"
    assert rows[0]["proposed_payload"] == payload
    assert rows[0]["evidence_refs"] == evidence

    ensure_mission_plan_seed(conn, run_id=str(result["run_id"]))
    plan = load_mission_plan(conn, run_id=str(result["run_id"]))
    assert plan["nodes"]
    first = plan["nodes"][0]
    assert first["sourceKind"] == "observer_seed"
    assert first["nodeKind"] == "mission"


def test_mission_lens_report_builds_actual_vs_should_artifact(tmp_path) -> None:
    from scripts.mission_lens import build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
            TextUnit("m2", "chat-a", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-fixture-v1")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [
                {"ts": "2026-03-08T10:00:00Z", "hour": 10, "kind": "chat", "detail": "Worked on notification routing feature thread", "meta": {"thread_id": "chat-a"}},
                {"ts": "2026-03-08T11:00:00Z", "hour": 11, "kind": "shell", "detail": "General shell work"},
            ],
            "frequency_by_hour": {"chat": [0] * 10 + [1] + [0] * 13, "shell": [0] * 11 + [1] + [0] * 12},
            "chat_threads": [{"thread_id": "chat-a", "title": "Notification routing feature", "message_count": 2, "source_ids": ["chat-a"]}],
        },
    )
    report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v1")
    assert report["planning_graph"]["nodes"]
    assert report["actual_allocation"]["left"]
    assert report["actual_allocation"]["right"]
    assert report["layered_graph"]["layers"]
    assert report["deadline_summary"]
    assert report["activity_rows"]
    assert "actual_mapping_summary" in report


def test_mission_lens_report_prefers_reviewed_actual_mapping_over_lexical_fallback(tmp_path) -> None:
    from scripts.mission_lens import build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
            TextUnit("m2", "chat-a", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-fixture-v2")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [
                {
                    "ts": "2026-03-08T10:00:00Z",
                    "hour": 10,
                    "kind": "chat",
                    "detail": "Worked on notification routing feature thread",
                    "meta": {"thread_id": "chat-a"},
                }
            ],
            "frequency_by_hour": {"chat": [0] * 10 + [1] + [0] * 13},
        },
    )
    report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v2")
    assert report["activity_rows"][0]["mappingSource"] == "lexical"
    activity_ref_id = report["activity_rows"][0]["activityRefId"]
    alternate_node = next(
        node["planNodeId"]
        for node in report["planning_graph"]["nodes"]
        if node["title"] == "new feature"
    )
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        upsert_mission_actual_mapping(
            conn,
            run_id="mission-lens-fixture-v2",
            mapping_id="map:fixture",
            activity_ref_id=activity_ref_id,
            plan_node_id=alternate_node,
            note="pytest reviewed mapping",
            receipts=[("author", "pytest")],
        )
        conn.commit()
    reviewed_report = build_mission_lens_report(
        itir_db_path=itir_db,
        sb_db_path=sb_db,
        date="2026-03-08",
        run_id="mission-lens-fixture-v2",
    )
    assert reviewed_report["activity_rows"][0]["mappingSource"] == "reviewed"
    assert reviewed_report["activity_rows"][0]["mappingStatus"] == "linked"
    assert reviewed_report["activity_rows"][0]["effectivePlanNodeId"] == alternate_node
    assert reviewed_report["activity_rows"][0]["matchedPlanNodeIds"] == [alternate_node]
    assert reviewed_report["summary"]["reviewed_actual_mapping_count"] == 1


def test_mission_lens_unlinked_reviewed_mapping_suppresses_lexical_fallback(tmp_path) -> None:
    from scripts.mission_lens import build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-fixture-v3")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [{"ts": "2026-03-08T10:00:00Z", "hour": 10, "kind": "chat", "detail": "Worked on notification routing feature thread"}],
        },
    )
    base_report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v3")
    activity_ref_id = base_report["activity_rows"][0]["activityRefId"]
    assert base_report["activity_rows"][0]["mappingSource"] == "lexical"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        upsert_mission_actual_mapping(
            conn,
            run_id="mission-lens-fixture-v3",
            mapping_id="map:fixture:unlink",
            activity_ref_id=activity_ref_id,
            plan_node_id=None,
            mapping_kind="reviewed_unlink",
            status="unlinked",
            note="pytest unlink",
            receipts=[("author", "pytest")],
        )
        current = load_mission_actual_mapping_current(conn, run_id="mission-lens-fixture-v3")
        assert current[0]["status"] == "unlinked"
        assert current[0]["planNodeId"] is None
        conn.commit()
    report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v3")
    row = report["activity_rows"][0]
    assert row["mappingSource"] == "reviewed"
    assert row["mappingStatus"] == "unlinked"
    assert row["matchedPlanNodeIds"] == []
    assert row["lexicalExplanation"] is None


def test_mission_lens_reassigned_mapping_becomes_effective_and_lexical_rows_explain_match(tmp_path) -> None:
    from scripts.mission_lens import build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
            TextUnit("m2", "chat-a", "chat_test_db", "[5/3/26 9:02 pm] Josh: Have you implemented the new feature?"),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-fixture-v4")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [{"ts": "2026-03-08T10:00:00Z", "hour": 10, "kind": "chat", "detail": "Worked on notification routing feature thread"}],
        },
    )
    lexical_report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v4")
    lexical_row = lexical_report["activity_rows"][0]
    assert lexical_row["mappingSource"] == "lexical"
    assert lexical_row["lexicalExplanation"]["matchedFields"] == ["detail"]
    assert lexical_row["recommendedAction"] in {"auto_link_safe", "review_primary_vs_alternative"}
    assert lexical_row["recommendationConfidence"] in {"high", "medium"}
    if lexical_row["lexicalExplanation"]["candidateCount"] > 1:
        assert lexical_row["lexicalExplanation"]["topAlternative"]["matchedTitle"]
        assert lexical_report["actual_mapping_summary"]["lexical_ambiguous"] == 1
        assert lexical_row["recommendedAction"] == "review_primary_vs_alternative"
        assert lexical_report["actual_mapping_summary"]["recommended_review"] == 1
    else:
        assert "topAlternative" not in lexical_row["lexicalExplanation"]
        assert lexical_report["actual_mapping_summary"]["lexical_ambiguous"] == 0
        assert lexical_row["recommendedAction"] == "auto_link_safe"
        assert lexical_report["actual_mapping_summary"]["recommended_safe"] == 1
    activity_ref_id = lexical_row["activityRefId"]
    alternate_node = next(
        node["planNodeId"]
        for node in lexical_report["planning_graph"]["nodes"]
        if node["title"] == "new feature"
    )
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        upsert_mission_actual_mapping(
            conn,
            run_id="mission-lens-fixture-v4",
            mapping_id="map:fixture:linked",
            activity_ref_id=activity_ref_id,
            plan_node_id=lexical_row["matchedPlanNodeIds"][0],
            status="linked",
            note="pytest initial link",
        )
        upsert_mission_actual_mapping(
            conn,
            run_id="mission-lens-fixture-v4",
            mapping_id="map:fixture:reassigned",
            activity_ref_id=activity_ref_id,
            plan_node_id=alternate_node,
            mapping_kind="reviewed_reassign",
            status="reassigned",
            note="pytest reassign",
        )
        conn.commit()
    report = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v4")
    row = report["activity_rows"][0]
    assert row["mappingSource"] == "reviewed"
    assert row["mappingStatus"] == "reassigned"
    assert row["effectivePlanNodeId"] == alternate_node
    assert row["matchedPlanNodeIds"] == [alternate_node]


def test_mission_lens_apply_safe_recommendations_only_applies_safe_rows(tmp_path) -> None:
    from scripts.mission_lens import apply_safe_recommendations, build_mission_lens_report
    from sb.dashboard_store_sqlite import DashboardKey, upsert_dashboard_payload

    itir_db = tmp_path / "itir.sqlite"
    sb_db = tmp_path / "dashboard.sqlite"
    with sqlite3.connect(itir_db) as conn:
        conn.row_factory = sqlite3.Row
        ensure_gwb_semantic_schema(conn)
        units = [
            TextUnit("m1", "chat-a", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
            TextUnit("m2", "chat-b", "chat_test_db", "[5/3/26 9:00 pm] Josh: We should track the new feature."),
        ]
        result = run_transcript_semantic_pipeline(conn, units, run_id="mission-lens-fixture-v5")
        build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)
    upsert_dashboard_payload(
        db_path=sb_db,
        key=DashboardKey(date="2026-03-08", view="daily", scope="all", window_days=0),
        payload={
            "date": "2026-03-08",
            "timeline": [
                {"ts": "2026-03-08T10:00:00Z", "hour": 10, "kind": "chat", "detail": "Worked on notification routing feature thread"},
                {"ts": "2026-03-08T11:00:00Z", "hour": 11, "kind": "chat", "detail": "General work"},
            ],
        },
    )
    before = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v5")
    safe_before = [
        row for row in before["activity_rows"] if row["recommendedAction"] == "auto_link_safe" and row["recommendationConfidence"] == "high"
    ]
    assert safe_before
    result = apply_safe_recommendations(
        itir_db_path=itir_db,
        sb_db_path=sb_db,
        date="2026-03-08",
        run_id="mission-lens-fixture-v5",
    )
    assert result["appliedCount"] == len(safe_before)
    after = build_mission_lens_report(itir_db_path=itir_db, sb_db_path=sb_db, date="2026-03-08", run_id="mission-lens-fixture-v5")
    for row in after["activity_rows"]:
        if row["activityRefId"] in result["appliedActivityRefIds"]:
            assert row["mappingSource"] == "reviewed"
            assert row["recommendedAction"] == "none"
    effective_rows = [
        row
        for row in after["effective_actual_mappings"]
        if row["activityRefId"] in result["appliedActivityRefIds"]
    ]
    assert effective_rows
    effective_receipt_pairs = {(receipt["kind"], receipt["value"]) for receipt in effective_rows[0]["receipts"]}
    assert ("authoring", "mission_lens_bulk_safe") in effective_receipt_pairs
    applied_history = [
        mapping
        for mapping in after["reviewed_actual_mappings"]
        if mapping["activityRefId"] in result["appliedActivityRefIds"]
    ]
    assert applied_history
    receipt_pairs = {(receipt["kind"], receipt["value"]) for receipt in applied_history[0]["receipts"]}
    assert ("authoring", "mission_lens_bulk_safe") in receipt_pairs
    assert any(kind == "recommendation_kind" for kind, _ in receipt_pairs)


def test_transcript_relation_summary_reports_counts_and_cues() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "journal-5", "text_file", "Alice is the guardian of Carol."),
        TextUnit("u2", "journal-5", "text_file", "Mary cared for Bob."),
        TextUnit("u3", "journal-5", "text_file", "Alice and Carol are friends."),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v7")
    from src.transcript_semantic.semantic import build_transcript_relation_summary

    summary = build_transcript_relation_summary(conn, run_id=result["run_id"], units=units)
    candidate_counts = summary["predicate_counts"]["candidate_only"]
    assert "abstained" in summary["predicate_counts"]
    assert candidate_counts["guardian_of"] >= 1
    assert candidate_counts["caregiver_of"] >= 1
    assert candidate_counts["friend_of"] >= 1
    assert summary["social_candidate_only_note"] == "All explicit social/care predicates remain candidate-only in this run."
    assert "guardian_of" in summary["top_cue_surfaces"]
    assert "caregiver_of" in summary["top_cue_surfaces"]
    assert summary["text_debug"]["event_count"] >= 1
    assert summary["text_debug"]["excluded_relation_count"] >= 0
    assert "mission_observer" in summary


def test_transcript_semantic_report_builds_mission_observer_followup_refs() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "slack-thread-1", "chat_test_db", "[5/3/26 8:45 pm] Josh: Please implement the notification routing feature by Friday."),
        TextUnit("u2", "slack-thread-1", "chat_test_db", "[5/3/26 9:02 pm] Josh: Hey have you implemented the new feature?"),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-mission-fixture-v1")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    mission = report["mission_observer"]
    assert mission["summary"]["mission_count"] >= 1
    assert mission["summary"]["followup_count"] >= 1
    assert mission["summary"]["linked_followup_count"] >= 1
    assert mission["summary"]["overlay_count"] >= 2
    resolved_followup = next(row for row in mission["followups"] if row["status"] == "linked")
    assert resolved_followup["resolvedTopicLabel"] == "notification routing feature"
    assert resolved_followup["deadline"] == "Friday"
    overlay = next(row for row in mission["sb_observer_overlays"] if row["status"] == "linked")
    assert overlay["observer_kind"] == "itir_mission_graph_v1"
    assert overlay["mission_refs"][0]["topic_label"] == "notification routing feature"
    assert any(ref["ref_kind"] == "resolved_topic" for ref in overlay["evidence_refs"])
    assert "promotion_status" not in overlay
    assert "support_direction" not in overlay
    assert "conflict_state" not in overlay
    assert "evidentiary_state" not in overlay
    assert "promotion_status" not in resolved_followup


def test_transcript_report_emits_grouped_source_documents_and_source_spans() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    units = [
        TextUnit("u1", "/tmp/demo-source.txt", "text_file", "Alice is the guardian of Carol."),
        TextUnit("u2", "/tmp/demo-source.txt", "text_file", "Mary cared for Bob."),
        TextUnit("u3", "chat-run-1", "chat_test_db", "Alice and Carol are friends."),
    ]
    result = run_transcript_semantic_pipeline(conn, units, run_id="transcript-fixture-v8")
    report = build_transcript_semantic_report(conn, run_id=result["run_id"], units=units)

    source_documents = {row["sourceDocumentId"]: row for row in report["source_documents"]}
    assert "/tmp/demo-source.txt" in source_documents
    assert "chat-run-1" in source_documents
    assert "Alice is the guardian of Carol." in source_documents["/tmp/demo-source.txt"]["text"]
    assert "Mary cared for Bob." in source_documents["/tmp/demo-source.txt"]["text"]

    debug_event = next(event for event in report["text_debug"]["events"] if event["eventId"] == "u1")
    assert debug_event["sourceDocumentId"] == "/tmp/demo-source.txt"
    assert isinstance(debug_event["sourceCharStart"], int)
    assert isinstance(debug_event["sourceCharEnd"], int)
    assert debug_event["sourceCharEnd"] > debug_event["sourceCharStart"]
