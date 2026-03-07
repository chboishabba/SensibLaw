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

