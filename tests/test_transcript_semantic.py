from __future__ import annotations

import sqlite3

from src.gwb_us_law.semantic import ensure_gwb_semantic_schema
from src.reporting.structure_report import TextUnit
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
