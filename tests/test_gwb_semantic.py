from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.gwb_us_law.linkage import ensure_gwb_us_law_schema, import_gwb_us_law_seed_payload
from src.gwb_us_law.semantic import (
    EntitySeed,
    _ensure_predicates,
    _insert_event_role,
    _policy_adjusted_confidence,
    _upsert_seed_entity,
    build_gwb_semantic_report,
    ensure_gwb_semantic_schema,
    run_gwb_semantic_pipeline,
)
from src.ontology.entity_bridge import ensure_bridge_schema, ensure_seeded_bridge_slice
from src.wiki_timeline.sqlite_store import persist_wiki_timeline_aoo_run


def test_gwb_semantic_pipeline_promotes_actor_and_relation_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "itir.sqlite"
    seed_path = Path(__file__).resolve().parents[1] / "data" / "ontology" / "gwb_us_law_linkage_seed_v1.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    timeline_payload = {
        "generated_at": "2026-03-07T00:00:00Z",
        "parser": {"name": "fixture"},
        "source_timeline": {"path": str(tmp_path / "wiki_timeline_gwb.json"), "snapshot": None},
        "events": [
            {
                "event_id": "ev1",
                "anchor": {"year": 2006, "text": "July 19, 2005"},
                "section": "Nominations",
                "text": "On July 19, 2005, Bush nominated John Roberts to the Supreme Court."
            },
            {
                "event_id": "ev2",
                "anchor": {"year": 2005, "text": "September 29, 2005"},
                "section": "Confirmations",
                "text": "John Roberts was confirmed by the Senate on September 29, 2005."
            },
            {
                "event_id": "ev3",
                "anchor": {"year": 2006, "text": "October 17, 2006"},
                "section": "Legislation",
                "text": "On October 17, 2006, Bush signed the Military Commissions Act of 2006 into law."
            },
            {
                "event_id": "ev4",
                "anchor": {"year": 2006, "text": "July 19, 2006"},
                "section": "Legislation",
                "text": "On July 19, 2006, Bush vetoed the Stem Cell Research Enhancement Act."
            },
            {
                "event_id": "ev5",
                "anchor": {"year": 2006, "text": "Unknown"},
                "section": "Politics",
                "text": "The administration and the President were under pressure from the court."
            },
            {
                "event_id": "ev6",
                "anchor": {"year": 2008, "text": "July 31, 2008"},
                "section": "Litigation",
                "text": "On July 31, 2008, a United States district court judge ruled that the Military Commissions Act of 2006 was unconstitutional."
            },
        ],
    }
    persist_wiki_timeline_aoo_run(db_path=db_path, out_payload=timeline_payload, timeline_path=tmp_path / "wiki_timeline_gwb.json")
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        ensure_bridge_schema(conn)
        ensure_seeded_bridge_slice(conn)
        ensure_gwb_us_law_schema(conn)
        ensure_gwb_semantic_schema(conn)
        import_gwb_us_law_seed_payload(conn, payload)
        result = run_gwb_semantic_pipeline(conn)
        report = build_gwb_semantic_report(conn, run_id=result["run_id"])

    promoted = {(row["predicate_key"], row["subject"]["canonical_key"], row["object"]["canonical_key"]) for row in report["promoted_relations"]}
    assert ("nominated", "actor:george_w_bush", "actor:john_roberts") in promoted
    assert ("confirmed_by", "actor:john_roberts", "actor:u_s_senate") in promoted
    assert ("signed", "actor:george_w_bush", "legal_ref:military_commissions_act_of_2006") in promoted
    assert ("vetoed", "actor:george_w_bush", "legal_ref:stem_cell_research_enhancement_act") in promoted
    assert ("ruled_by", "legal_ref:military_commissions_act_of_2006", "actor:united_states_district_court") in promoted

    unresolved_surfaces = {row["surface_text"] for row in report["unresolved_mentions"]}
    assert "the administration" in unresolved_surfaces
    assert "the President" in unresolved_surfaces
    assert "the court" in unresolved_surfaces
    signed_row = next(row for row in report["promoted_relations"] if row["predicate_key"] == "signed")
    signed_receipts = {(receipt["kind"], receipt["value"]) for receipt in signed_row["receipts"]}
    assert ("rule_type", "executive_action") in signed_receipts
    assert ("promotion_status", "promoted") in signed_receipts

    per_entity = {row["entity"]["canonical_key"]: row for row in report["per_entity"]}
    assert per_entity["actor:george_w_bush"]["promoted_relation_count"] >= 3
    assert report["summary"]["candidate_only_relation_count"] >= 0
    assert report["text_debug"]["events"]
    assert report["source_documents"]
    assert report["source_documents"][0]["text"]
    assert report["review_summary"]["predicate_counts"]["promoted"]["signed"] >= 1
    assert report["review_summary"]["text_debug"]["relation_count"] >= 1
    signed_debug = next(
        relation
        for event in report["text_debug"]["events"]
        for relation in event["relations"]
        if relation["predicateKey"] == "signed"
    )
    assert signed_debug["family"] == "governance"
    assert any(anchor["source"] in {"mention", "receipt", "label_fallback"} for anchor in signed_debug["anchors"])
    assert all(isinstance(anchor["charStart"], int) and isinstance(anchor["charEnd"], int) for anchor in signed_debug["anchors"])
    assert all(anchor["sourceArtifactId"] for anchor in signed_debug["anchors"])
    signed_event = next(event for event in report["text_debug"]["events"] if any(rel["predicateKey"] == "signed" for rel in event["relations"]))
    assert signed_event["sourceDocumentId"]
    assert isinstance(signed_event["sourceCharStart"], int)
    assert isinstance(signed_event["sourceCharEnd"], int)


def test_gwb_semantic_schema_populates_shared_actor_aliases_and_role_vocab() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    _ensure_predicates(conn)
    bush_entity_id = _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="actor",
            canonical_key="actor:george_w_bush",
            canonical_label="George W. Bush",
            actor_kind="person_actor",
            aliases=("George W. Bush", "George Bush", "Bush"),
        ),
    )
    _insert_event_role(
        conn,
        run_id="gwb-shared-actor-v1",
        event_id="ev1",
        role_kind="agent",
        entity_id=bush_entity_id,
        note="test",
    )

    bush_entity = conn.execute(
        """
        SELECT entity_id, shared_actor_id
        FROM semantic_entities
        WHERE canonical_key = 'actor:george_w_bush'
        """
    ).fetchone()
    assert bush_entity is not None
    assert bush_entity["shared_actor_id"] is not None

    aliases = {
        row["alias_text"]
        for row in conn.execute(
            """
            SELECT aa.alias_text
            FROM actor_aliases AS aa
            WHERE aa.actor_id = ?
            """,
            (int(bush_entity["shared_actor_id"]),),
        ).fetchall()
    }
    assert {"George W. Bush", "George Bush", "Bush"} <= aliases

    role_vocab = {
        row["role_key"]: row["display_label"]
        for row in conn.execute("SELECT role_key, display_label FROM event_role_vocab").fetchall()
    }
    assert role_vocab["agent"] == "Agent"
    assert role_vocab["theme"] == "Theme"

    rule_types = {
        row["rule_type_key"]: row["output_kind"]
        for row in conn.execute("SELECT rule_type_key, output_kind FROM semantic_rule_types").fetchall()
    }
    assert rule_types["authority_invocation"] == "semantic_relation"
    assert rule_types["actor_role"] == "event_role"

    slots = {
        (row["rule_type_key"], row["slot_key"], row["selector_type"], row["required"])
        for row in conn.execute(
            """
            SELECT rule_type_key, slot_key, selector_type, required
            FROM semantic_rule_slots
            """
        ).fetchall()
    }
    assert ("actor_role", "party", "prep_for", 1) in slots
    assert ("review_relation", "forum", "forum_context", 0) in slots

    policies = {
        row["predicate_key"]: (
            row["rule_type_key"],
            row["min_confidence"],
            row["required_evidence_count"],
        )
        for row in conn.execute(
            """
            SELECT predicate_key, rule_type_key, min_confidence, required_evidence_count
            FROM semantic_promotion_policies
            """
        ).fetchall()
    }
    assert policies["signed"] == ("executive_action", "medium", 3)
    assert policies["ruled_by"] == ("review_relation", "medium", 2)


def test_policy_adjusted_confidence_downgrades_under_evidenced_cases() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_gwb_semantic_schema(conn)
    _ensure_predicates(conn)

    assert (
        _policy_adjusted_confidence(
            conn,
            predicate_key="signed",
            receipts=[("subject", "actor:george_w_bush"), ("verb", "signed")],
            legacy_confidence="high",
        )
        == "low"
    )
    assert (
        _policy_adjusted_confidence(
            conn,
            predicate_key="signed",
            receipts=[("subject", "actor:george_w_bush")],
            legacy_confidence="medium",
        )
        == "abstain"
    )
