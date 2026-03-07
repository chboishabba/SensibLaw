from __future__ import annotations

import sqlite3

from src.gwb_us_law.semantic import (
    PIPELINE_VERSION,
    EntitySeed,
    _ensure_predicates,
    _insert_cluster_and_resolution,
    _insert_event_role,
    _insert_relation_candidate,
    _upsert_seed_entity,
    ensure_gwb_semantic_schema,
)


def test_frozen_semantic_shape_handles_australian_review_pattern_without_schema_change() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    predicate_ids = _ensure_predicates(conn)

    high_court_id = _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="actor",
            canonical_key="actor:high_court_of_australia",
            canonical_label="High Court of Australia",
            actor_kind="institution_actor",
            classification_tag="court",
            aliases=("High Court of Australia",),
        ),
    )
    plaintiff_id = _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="legal_ref",
            canonical_key="legal_ref:plaintiff_s157_2002_v_commonwealth",
            canonical_label="Plaintiff S157/2002 v Commonwealth",
            ref_kind="case_ref",
            source_title="Plaintiff S157/2002 v Commonwealth",
            aliases=("Plaintiff S157/2002 v Commonwealth",),
        ),
    )
    native_title_id = _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="legal_ref",
            canonical_key="legal_ref:native_title_new_south_wales_act_1994",
            canonical_label="Native Title (New South Wales) Act 1994",
            ref_kind="act_ref",
            source_title="Native Title (New South Wales) Act 1994",
            aliases=("Native Title (New South Wales) Act 1994",),
        ),
    )

    _, resolution_id = _insert_cluster_and_resolution(
        conn,
        run_id="au-cross-v1",
        event_id="ev-au-1",
        mention_kind="actor",
        canonical_key_hint=None,
        surface_text="the Court",
        source_rule="au_fixture_discourse_surface_v1",
        resolved_entity_id=None,
        resolution_status="abstained",
        resolution_rule="title_requires_stronger_context_v1",
        receipts=[("surface", "the Court"), ("reason", "ambiguous_forum_reference")],
    )
    _insert_event_role(
        conn,
        run_id="au-cross-v1",
        event_id="ev-au-1",
        role_kind="forum",
        entity_id=high_court_id,
        note="au_review_fixture_v1",
    )
    _insert_event_role(
        conn,
        run_id="au-cross-v1",
        event_id="ev-au-1",
        role_kind="theme",
        entity_id=plaintiff_id,
        note="au_review_fixture_v1",
    )
    _insert_event_role(
        conn,
        run_id="au-cross-v1",
        event_id="ev-au-1",
        role_kind="authority",
        entity_id=native_title_id,
        note="au_review_fixture_v1",
    )
    candidate_id = _insert_relation_candidate(
        conn,
        run_id="au-cross-v1",
        event_id="ev-au-1",
        subject_entity_id=plaintiff_id,
        predicate_id=predicate_ids["challenged_in"],
        object_entity_id=high_court_id,
        confidence_tier="medium",
        receipts=[
            ("subject", "legal_ref:plaintiff_s157_2002_v_commonwealth"),
            ("verb", "challenged_in"),
            ("object_actor", "actor:high_court_of_australia"),
            ("authority", "legal_ref:native_title_new_south_wales_act_1994"),
        ],
    )

    actor_row = conn.execute(
        """
        SELECT actor_kind, classification_tag
        FROM semantic_entity_actors
        WHERE entity_id = ?
        """,
        (high_court_id,),
    ).fetchone()
    resolution_row = conn.execute(
        """
        SELECT resolution_status, resolution_rule, pipeline_version
        FROM semantic_mention_resolutions
        WHERE resolution_id = ?
        """,
        (resolution_id,),
    ).fetchone()
    candidate_row = conn.execute(
        """
        SELECT promotion_status, confidence_tier, pipeline_version
        FROM semantic_relation_candidates
        WHERE candidate_id = ?
        """,
        (candidate_id,),
    ).fetchone()
    promoted_row = conn.execute(
        """
        SELECT r.event_id, p.predicate_key, se.canonical_key AS subject_key, oe.canonical_key AS object_key
        FROM semantic_relations AS r
        JOIN semantic_predicate_vocab AS p ON p.predicate_id = r.predicate_id
        JOIN semantic_entities AS se ON se.entity_id = r.subject_entity_id
        JOIN semantic_entities AS oe ON oe.entity_id = r.object_entity_id
        WHERE r.candidate_id = ?
        """,
        (candidate_id,),
    ).fetchone()

    assert actor_row["actor_kind"] == "institution_actor"
    assert actor_row["classification_tag"] == "court"
    assert resolution_row["resolution_status"] == "abstained"
    assert resolution_row["resolution_rule"] == "title_requires_stronger_context_v1"
    assert resolution_row["pipeline_version"] == PIPELINE_VERSION
    assert candidate_row["promotion_status"] == "promoted"
    assert candidate_row["confidence_tier"] == "medium"
    assert candidate_row["pipeline_version"] == PIPELINE_VERSION
    assert promoted_row["event_id"] == "ev-au-1"
    assert promoted_row["predicate_key"] == "challenged_in"
    assert promoted_row["subject_key"] == "legal_ref:plaintiff_s157_2002_v_commonwealth"
    assert promoted_row["object_key"] == "actor:high_court_of_australia"
