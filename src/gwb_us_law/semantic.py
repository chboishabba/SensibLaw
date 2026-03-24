from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Mapping

from src.gwb_us_law.linkage import (
    _pick_best_run_for_timeline_suffix,
    build_gwb_us_law_linkage_report,
    run_gwb_us_law_linkage,
)
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized


PIPELINE_VERSION = "gwb_semantic_v1"

_EVENT_ROLE_VOCAB: tuple[tuple[str, str, str], ...] = (
    ("agent", "Agent", "core_participant"),
    ("authority", "Authority", "governing_context"),
    ("forum", "Forum", "governing_context"),
    ("legal_representative", "Legal Representative", "legal_context"),
    ("mentioned_entity", "Mentioned Entity", "general_context"),
    ("office_context", "Office Context", "governing_context"),
    ("patient", "Patient", "core_participant"),
    ("related_person", "Related Person", "general_context"),
    ("speaker", "Speaker", "communicative_context"),
    ("subject", "Subject", "core_participant"),
    ("theme", "Theme", "core_participant"),
)

_SEMANTIC_RULE_TYPES: tuple[tuple[str, str, str, str], ...] = (
    (
        "governance_action",
        "Governance Action",
        "Executive, legislative, or institutional actions that attach a promoted semantic relation to an event.",
        "semantic_relation",
    ),
    (
        "executive_action",
        "Executive Action",
        "Executive action relations anchored to a specific event.",
        "semantic_relation",
    ),
    (
        "review_relation",
        "Review Relation",
        "Review, appeal, and adjudicative relations that remain event-scoped.",
        "semantic_relation",
    ),
    (
        "authority_invocation",
        "Authority Invocation",
        "Authority and precedent invocation relations derived from explicit legal-reference cues.",
        "semantic_relation",
    ),
    (
        "actor_role",
        "Actor Role",
        "Participation/context assignments such as legal representation roles.",
        "event_role",
    ),
    (
        "conversational_relation",
        "Conversational Relation",
        "Conversational reply or turn-taking relations between event participants.",
        "semantic_relation",
    ),
    (
        "state_signal",
        "State Signal",
        "Explicit affect/state cues that may remain candidate-only under conservative promotion gates.",
        "semantic_relation",
    ),
    (
        "social_relation",
        "Social Relation",
        "Explicit text-local kinship, guardianship, care, or friendship relations between named actors.",
        "semantic_relation",
    ),
)

_SEMANTIC_SLOT_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("subject", "actor", "Primary subject entity for the rule match."),
    ("object", "semantic_entity", "Primary object entity for the rule match."),
    ("verb", "lexical_trigger", "Lexical trigger or cue verb for the rule match."),
    ("actor", "actor", "Actor participant for role assignment rules."),
    ("party", "litigant", "Litigant/party slot used by role assignment rules."),
    ("role_marker", "representation_marker", "Role cue surface such as appeared for / counsel for."),
    ("forum", "court", "Forum or court context attached to a review/authority rule."),
    ("speaker", "actor", "Speaker participant for conversational rules."),
    ("state", "state", "Explicit affect/state concept attached to a participant."),
    ("relation_marker", "lexical_trigger", "Explicit kinship/guardian/care/friendship marker used by social relation rules."),
)

_SEMANTIC_RULE_SLOTS: tuple[tuple[str, str, str, int, int], ...] = (
    ("governance_action", "subject", "subject", 1, 1),
    ("governance_action", "verb", "verb", 1, 2),
    ("governance_action", "object", "object", 1, 3),
    ("executive_action", "subject", "subject", 1, 1),
    ("executive_action", "verb", "verb", 1, 2),
    ("executive_action", "object", "object", 1, 3),
    ("review_relation", "subject", "subject", 1, 1),
    ("review_relation", "verb", "verb", 1, 2),
    ("review_relation", "object", "object", 1, 3),
    ("review_relation", "forum", "forum_context", 0, 4),
    ("authority_invocation", "subject", "subject", 1, 1),
    ("authority_invocation", "verb", "verb", 1, 2),
    ("authority_invocation", "object", "nearest_legal_ref", 1, 3),
    ("authority_invocation", "forum", "forum_context", 0, 4),
    ("actor_role", "actor", "subject", 1, 1),
    ("actor_role", "role_marker", "verb", 1, 2),
    ("actor_role", "party", "prep_for", 1, 3),
    ("conversational_relation", "speaker", "speaker_context", 1, 1),
    ("conversational_relation", "verb", "verb", 1, 2),
    ("conversational_relation", "object", "object", 1, 3),
    ("state_signal", "subject", "subject", 1, 1),
    ("state_signal", "verb", "verb", 1, 2),
    ("state_signal", "state", "object", 1, 3),
    ("social_relation", "subject", "subject", 1, 1),
    ("social_relation", "relation_marker", "verb", 1, 2),
    ("social_relation", "object", "object", 1, 3),
)

_SEMANTIC_PROMOTION_POLICIES: tuple[tuple[str, str, str, int, int, str], ...] = (
    ("nominated", "governance_action", "medium", 3, 0, "subject + verb + object actor required for promotion"),
    ("confirmed_by", "governance_action", "medium", 3, 0, "subject + verb + confirming authority required for promotion"),
    ("signed", "executive_action", "medium", 3, 0, "subject + verb + legal reference required for promotion"),
    ("vetoed", "executive_action", "medium", 3, 0, "subject + verb + legal reference required for promotion"),
    ("authorized", "executive_action", "medium", 3, 0, "event-scoped executive authorization requires complete subject/object evidence"),
    ("ruled_by", "review_relation", "medium", 2, 0, "review/forum relation requires explicit cue plus resolved court/object"),
    ("challenged_in", "review_relation", "medium", 2, 0, "challenge relation requires explicit cue plus resolved forum/object"),
    ("subject_of_review_by", "review_relation", "medium", 2, 0, "review relation requires explicit cue plus resolved court/object"),
    ("funded_by", "governance_action", "medium", 2, 0, "funding relation requires explicit actor/object support"),
    ("sanctioned", "governance_action", "medium", 2, 0, "sanction relation requires explicit actor/object support"),
    ("appealed", "review_relation", "medium", 3, 0, "appeal promotion requires subject + verb + forum/object evidence"),
    ("challenged", "review_relation", "medium", 3, 0, "challenge promotion requires subject + verb + object evidence"),
    ("heard_by", "review_relation", "medium", 3, 0, "hearing promotion requires subject + verb + forum/object evidence"),
    ("decided_by", "review_relation", "medium", 3, 0, "decision promotion requires subject + verb + forum/object evidence"),
    ("applied", "authority_invocation", "medium", 3, 0, "authority invocation requires subject + verb + legal reference evidence"),
    ("followed", "authority_invocation", "medium", 3, 0, "authority invocation requires subject + verb + legal reference evidence"),
    ("distinguished", "authority_invocation", "medium", 3, 0, "authority invocation requires subject + verb + legal reference evidence"),
    ("held_that", "authority_invocation", "medium", 3, 0, "holding relation requires subject + verb + object evidence"),
    ("replied_to", "conversational_relation", "high", 3, 0, "conversational replies remain conservative unless speaker/object evidence is complete"),
    ("felt_state", "state_signal", "high", 3, 0, "affect/state relations remain candidate-first unless explicit state evidence is complete"),
    ("sibling_of", "social_relation", "high", 3, 0, "explicit kinship relations remain candidate-first unless stronger cross-evidence exists"),
    ("parent_of", "social_relation", "high", 3, 0, "explicit kinship relations remain candidate-first unless stronger cross-evidence exists"),
    ("child_of", "social_relation", "high", 3, 0, "explicit kinship relations remain candidate-first unless stronger cross-evidence exists"),
    ("spouse_of", "social_relation", "high", 3, 0, "explicit partner relations remain candidate-first unless stronger cross-evidence exists"),
    ("friend_of", "social_relation", "high", 3, 0, "explicit friendship relations remain candidate-first unless stronger cross-evidence exists"),
    ("guardian_of", "social_relation", "high", 3, 0, "explicit guardianship relations remain candidate-first unless stronger cross-evidence exists"),
    ("caregiver_of", "social_relation", "high", 3, 0, "explicit care relations remain candidate-first unless stronger cross-evidence exists"),
)


def ensure_gwb_semantic_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actors (
          actor_id INTEGER PRIMARY KEY,
          actor_kind TEXT NOT NULL,
          canonical_key TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'deterministic_v1',
          pipeline_version TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actor_aliases (
          alias_id INTEGER PRIMARY KEY,
          actor_id INTEGER NOT NULL REFERENCES actors(actor_id) ON DELETE CASCADE,
          alias_text TEXT NOT NULL,
          normalized_alias TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_ref TEXT,
          review_status TEXT NOT NULL DEFAULT 'deterministic_v1',
          is_primary INTEGER NOT NULL DEFAULT 0,
          pipeline_version TEXT NOT NULL,
          UNIQUE(actor_id, normalized_alias, source_kind, source_ref)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS actor_merges (
          merge_id INTEGER PRIMARY KEY,
          source_actor_id INTEGER NOT NULL REFERENCES actors(actor_id) ON DELETE CASCADE,
          target_actor_id INTEGER NOT NULL REFERENCES actors(actor_id) ON DELETE CASCADE,
          merge_rule TEXT NOT NULL,
          source_ref TEXT,
          note TEXT,
          pipeline_version TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_role_vocab (
          role_key TEXT PRIMARY KEY,
          display_label TEXT NOT NULL,
          role_family TEXT NOT NULL,
          active_v1 INTEGER NOT NULL DEFAULT 1,
          review_status TEXT NOT NULL DEFAULT 'deterministic_v1',
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_entities (
          entity_id INTEGER PRIMARY KEY,
          entity_kind TEXT NOT NULL,
          canonical_key TEXT NOT NULL UNIQUE,
          canonical_label TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'deterministic_v1',
          pipeline_version TEXT NOT NULL,
          shared_actor_id INTEGER REFERENCES actors(actor_id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_entity_actors (
          entity_id INTEGER PRIMARY KEY REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          actor_kind TEXT NOT NULL,
          classification_tag TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_entity_offices (
          entity_id INTEGER PRIMARY KEY REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          office_kind TEXT NOT NULL DEFAULT 'office'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_entity_legal_refs (
          entity_id INTEGER PRIMARY KEY REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          ref_kind TEXT NOT NULL,
          source_title TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_office_holdings (
          office_holding_id INTEGER PRIMARY KEY,
          person_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          office_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          start_date TEXT,
          end_date TEXT,
          source TEXT,
          pipeline_version TEXT NOT NULL,
          UNIQUE (person_entity_id, office_entity_id, start_date, end_date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_mention_clusters (
          cluster_id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          mention_kind TEXT NOT NULL,
          canonical_key_hint TEXT,
          surface_text TEXT NOT NULL,
          normalized_surface TEXT NOT NULL,
          source_rule TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_mention_resolutions (
          resolution_id INTEGER PRIMARY KEY,
          cluster_id INTEGER NOT NULL UNIQUE REFERENCES semantic_mention_clusters(cluster_id) ON DELETE CASCADE,
          resolved_entity_id INTEGER REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          resolution_status TEXT NOT NULL,
          resolution_rule TEXT NOT NULL,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_mention_resolution_receipts (
          resolution_id INTEGER NOT NULL REFERENCES semantic_mention_resolutions(resolution_id) ON DELETE CASCADE,
          receipt_order INTEGER NOT NULL,
          reason_kind TEXT NOT NULL,
          reason_value TEXT NOT NULL,
          PRIMARY KEY (resolution_id, receipt_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_event_roles (
          role_id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          role_kind TEXT NOT NULL,
          entity_id INTEGER REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          cluster_id INTEGER REFERENCES semantic_mention_clusters(cluster_id) ON DELETE CASCADE,
          note TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_predicate_vocab (
          predicate_id INTEGER PRIMARY KEY,
          predicate_key TEXT NOT NULL UNIQUE,
          display_label TEXT NOT NULL,
          predicate_family TEXT NOT NULL,
          is_directed INTEGER NOT NULL DEFAULT 1,
          inverse_predicate_key TEXT,
          promotion_rule_key TEXT NOT NULL,
          active_v1 INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_relation_candidates (
          candidate_id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          subject_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          predicate_id INTEGER NOT NULL REFERENCES semantic_predicate_vocab(predicate_id) ON DELETE CASCADE,
          object_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          promotion_status TEXT NOT NULL,
          confidence_tier TEXT NOT NULL,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_relation_candidate_receipts (
          candidate_id INTEGER NOT NULL REFERENCES semantic_relation_candidates(candidate_id) ON DELETE CASCADE,
          receipt_order INTEGER NOT NULL,
          reason_kind TEXT NOT NULL,
          reason_value TEXT NOT NULL,
          PRIMARY KEY (candidate_id, receipt_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_relations (
          relation_id INTEGER PRIMARY KEY,
          candidate_id INTEGER NOT NULL UNIQUE REFERENCES semantic_relation_candidates(candidate_id) ON DELETE CASCADE,
          subject_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          predicate_id INTEGER NOT NULL REFERENCES semantic_predicate_vocab(predicate_id) ON DELETE CASCADE,
          object_entity_id INTEGER NOT NULL REFERENCES semantic_entities(entity_id) ON DELETE CASCADE,
          event_id TEXT NOT NULL,
          confidence_tier TEXT NOT NULL,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_relation_receipts (
          relation_id INTEGER NOT NULL REFERENCES semantic_relations(relation_id) ON DELETE CASCADE,
          receipt_order INTEGER NOT NULL,
          reason_kind TEXT NOT NULL,
          reason_value TEXT NOT NULL,
          PRIMARY KEY (relation_id, receipt_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_rule_types (
          rule_type_key TEXT PRIMARY KEY,
          display_label TEXT NOT NULL,
          description TEXT NOT NULL,
          output_kind TEXT NOT NULL,
          active_v1 INTEGER NOT NULL DEFAULT 1,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_slot_definitions (
          slot_key TEXT PRIMARY KEY,
          slot_type TEXT NOT NULL,
          description TEXT NOT NULL,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_rule_slots (
          rule_type_key TEXT NOT NULL REFERENCES semantic_rule_types(rule_type_key) ON DELETE CASCADE,
          slot_key TEXT NOT NULL REFERENCES semantic_slot_definitions(slot_key) ON DELETE CASCADE,
          selector_type TEXT NOT NULL,
          required INTEGER NOT NULL DEFAULT 1,
          slot_order INTEGER NOT NULL,
          pipeline_version TEXT NOT NULL,
          PRIMARY KEY (rule_type_key, slot_key, selector_type)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_promotion_policies (
          predicate_key TEXT PRIMARY KEY REFERENCES semantic_predicate_vocab(predicate_key) ON DELETE CASCADE,
          rule_type_key TEXT NOT NULL REFERENCES semantic_rule_types(rule_type_key) ON DELETE CASCADE,
          min_confidence TEXT NOT NULL,
          required_evidence_count INTEGER NOT NULL,
          allow_conflict INTEGER NOT NULL DEFAULT 0,
          policy_note TEXT,
          pipeline_version TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_review_submissions (
          submission_id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          run_id TEXT NOT NULL,
          corpus_label TEXT NOT NULL,
          event_id TEXT NOT NULL,
          relation_id TEXT,
          anchor_key TEXT,
          action_kind TEXT NOT NULL,
          proposed_payload_json TEXT NOT NULL,
          operator_provenance_json TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_review_evidence_refs (
          submission_id TEXT NOT NULL REFERENCES semantic_review_submissions(submission_id) ON DELETE CASCADE,
          evidence_order INTEGER NOT NULL,
          evidence_payload_json TEXT NOT NULL,
          PRIMARY KEY (submission_id, evidence_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_runs (
          run_id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          pipeline_version TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_nodes (
          mission_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          node_kind TEXT NOT NULL,
          topic_label TEXT NOT NULL,
          normalized_topic TEXT NOT NULL,
          status TEXT NOT NULL,
          confidence TEXT NOT NULL,
          source_id TEXT NOT NULL,
          deadline TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_node_event_refs (
          mission_id TEXT NOT NULL REFERENCES mission_nodes(mission_id) ON DELETE CASCADE,
          event_id TEXT NOT NULL,
          PRIMARY KEY (mission_id, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_node_owner_refs (
          mission_id TEXT NOT NULL REFERENCES mission_nodes(mission_id) ON DELETE CASCADE,
          owner_order INTEGER NOT NULL,
          entity_id INTEGER,
          label TEXT NOT NULL,
          PRIMARY KEY (mission_id, owner_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_edges (
          edge_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          edge_kind TEXT NOT NULL,
          source_node_id TEXT REFERENCES mission_nodes(mission_id) ON DELETE CASCADE,
          target_node_id TEXT REFERENCES mission_nodes(mission_id) ON DELETE CASCADE,
          activity_event_id TEXT,
          target_event_id TEXT,
          source_id TEXT,
          speaker TEXT,
          followup_topic TEXT,
          status TEXT NOT NULL,
          confidence TEXT NOT NULL,
          deadline TEXT,
          note TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_evidence_refs (
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          owner_kind TEXT NOT NULL,
          owner_id TEXT NOT NULL,
          evidence_order INTEGER NOT NULL,
          evidence_payload_json TEXT NOT NULL,
          PRIMARY KEY (run_id, owner_kind, owner_id, evidence_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_observer_overlays (
          annotation_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          activity_event_id TEXT NOT NULL,
          sb_state_id TEXT,
          observer_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          confidence TEXT NOT NULL,
          provenance_json TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_overlay_refs (
          annotation_id TEXT NOT NULL REFERENCES mission_observer_overlays(annotation_id) ON DELETE CASCADE,
          ref_group TEXT NOT NULL,
          ref_order INTEGER NOT NULL,
          ref_payload_json TEXT NOT NULL,
          PRIMARY KEY (annotation_id, ref_group, ref_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_plan_nodes (
          plan_node_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          node_kind TEXT NOT NULL,
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          source_kind TEXT NOT NULL DEFAULT 'manual',
          mission_id TEXT REFERENCES mission_nodes(mission_id) ON DELETE SET NULL,
          parent_plan_node_id TEXT REFERENCES mission_plan_nodes(plan_node_id) ON DELETE SET NULL,
          target_weight REAL NOT NULL DEFAULT 1.0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_plan_edges (
          edge_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          from_plan_node_id TEXT NOT NULL REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          to_plan_node_id TEXT NOT NULL REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          edge_kind TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_plan_deadlines (
          plan_node_id TEXT PRIMARY KEY REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          raw_phrase TEXT,
          due_start TEXT,
          due_end TEXT,
          certainty_kind TEXT NOT NULL DEFAULT 'ambiguous',
          urgency_level TEXT NOT NULL DEFAULT 'medium',
          flexibility_level TEXT NOT NULL DEFAULT 'flexible'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_plan_receipts (
          plan_node_id TEXT NOT NULL REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          receipt_order INTEGER NOT NULL,
          receipt_kind TEXT NOT NULL,
          receipt_value TEXT NOT NULL,
          PRIMARY KEY (plan_node_id, receipt_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_actual_mappings (
          mapping_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          activity_ref_id TEXT NOT NULL,
          plan_node_id TEXT REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          mapping_kind TEXT NOT NULL DEFAULT 'reviewed_link',
          status TEXT NOT NULL DEFAULT 'linked',
          confidence_tier TEXT NOT NULL DEFAULT 'high',
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_actual_mapping_receipts (
          mapping_id TEXT NOT NULL REFERENCES mission_actual_mappings(mapping_id) ON DELETE CASCADE,
          receipt_order INTEGER NOT NULL,
          receipt_kind TEXT NOT NULL,
          receipt_value TEXT NOT NULL,
          PRIMARY KEY (mapping_id, receipt_order)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_actual_mapping_current (
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          activity_ref_id TEXT NOT NULL,
          mapping_id TEXT NOT NULL REFERENCES mission_actual_mappings(mapping_id) ON DELETE CASCADE,
          plan_node_id TEXT REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          mapping_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          confidence_tier TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (run_id, activity_ref_id)
        )
        """
    )
    _ensure_mission_actual_mappings_schema(conn)
    _ensure_semantic_entities_shared_actor_column(conn)
    _ensure_event_role_vocab(conn)
    _ensure_semantic_rule_metadata(conn)


def _ensure_mission_actual_mappings_schema(conn: sqlite3.Connection) -> None:
    columns = {
        str(row["name"]): row
        for row in conn.execute("PRAGMA table_info(mission_actual_mappings)").fetchall()
    }
    needs_rebuild = False
    plan_col = columns.get("plan_node_id")
    if plan_col is not None and int(plan_col["notnull"]) != 0:
        needs_rebuild = True
    index_rows = conn.execute("PRAGMA index_list(mission_actual_mappings)").fetchall()
    if any(
        int(row["unique"]) and str(row["origin"]) != "pk" and str(row["name"]).startswith("sqlite_autoindex_mission_actual_mappings_")
        for row in index_rows
    ):
        needs_rebuild = True
    if not needs_rebuild:
        return
    conn.execute("ALTER TABLE mission_actual_mappings RENAME TO mission_actual_mappings_legacy")
    conn.execute(
        """
        CREATE TABLE mission_actual_mappings (
          mapping_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES mission_runs(run_id) ON DELETE CASCADE,
          activity_ref_id TEXT NOT NULL,
          plan_node_id TEXT REFERENCES mission_plan_nodes(plan_node_id) ON DELETE CASCADE,
          mapping_kind TEXT NOT NULL DEFAULT 'reviewed_link',
          status TEXT NOT NULL DEFAULT 'linked',
          confidence_tier TEXT NOT NULL DEFAULT 'high',
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        INSERT INTO mission_actual_mappings(
          mapping_id, run_id, activity_ref_id, plan_node_id, mapping_kind, status, confidence_tier, note, created_at
        )
        SELECT mapping_id, run_id, activity_ref_id, plan_node_id, mapping_kind, status, confidence_tier, note, created_at
        FROM mission_actual_mappings_legacy
        """
    )
    conn.execute("DROP TABLE mission_actual_mappings_legacy")


def _ensure_semantic_entities_shared_actor_column(conn: sqlite3.Connection) -> None:
    columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(semantic_entities)").fetchall()}
    if "shared_actor_id" not in columns:
        conn.execute("ALTER TABLE semantic_entities ADD COLUMN shared_actor_id INTEGER REFERENCES actors(actor_id) ON DELETE SET NULL")


def _display_label_from_role_key(role_key: str) -> str:
    return role_key.replace("_", " ").title()


def _ensure_event_role_vocab(conn: sqlite3.Connection) -> None:
    for role_key, display_label, role_family in _EVENT_ROLE_VOCAB:
        conn.execute(
            """
            INSERT INTO event_role_vocab(role_key, display_label, role_family, active_v1, review_status, pipeline_version)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(role_key) DO UPDATE SET
              display_label=excluded.display_label,
              role_family=excluded.role_family,
              active_v1=excluded.active_v1,
              review_status=excluded.review_status,
              pipeline_version=excluded.pipeline_version
            """,
            (role_key, display_label, role_family, 1, "deterministic_v1", PIPELINE_VERSION),
        )


def _ensure_event_role_vocab_entry(conn: sqlite3.Connection, role_key: str) -> None:
    row = conn.execute("SELECT 1 FROM event_role_vocab WHERE role_key = ?", (role_key,)).fetchone()
    if row is not None:
        return
    conn.execute(
        """
        INSERT INTO event_role_vocab(role_key, display_label, role_family, active_v1, review_status, pipeline_version)
        VALUES (?,?,?,?,?,?)
        """,
        (role_key, _display_label_from_role_key(role_key), "semantic_role", 1, "deterministic_v1", PIPELINE_VERSION),
    )


def _ensure_semantic_rule_metadata(conn: sqlite3.Connection) -> None:
    for rule_type_key, display_label, description, output_kind in _SEMANTIC_RULE_TYPES:
        conn.execute(
            """
            INSERT INTO semantic_rule_types(
              rule_type_key, display_label, description, output_kind, active_v1, pipeline_version
            ) VALUES (?,?,?,?,?,?)
            ON CONFLICT(rule_type_key)
            DO UPDATE SET display_label=excluded.display_label,
                          description=excluded.description,
                          output_kind=excluded.output_kind,
                          active_v1=excluded.active_v1,
                          pipeline_version=excluded.pipeline_version
            """,
            (rule_type_key, display_label, description, output_kind, 1, PIPELINE_VERSION),
        )
    for slot_key, slot_type, description in _SEMANTIC_SLOT_DEFINITIONS:
        conn.execute(
            """
            INSERT INTO semantic_slot_definitions(slot_key, slot_type, description, pipeline_version)
            VALUES (?,?,?,?)
            ON CONFLICT(slot_key)
            DO UPDATE SET slot_type=excluded.slot_type,
                          description=excluded.description,
                          pipeline_version=excluded.pipeline_version
            """,
            (slot_key, slot_type, description, PIPELINE_VERSION),
        )
    for rule_type_key, slot_key, selector_type, required, slot_order in _SEMANTIC_RULE_SLOTS:
        conn.execute(
            """
            INSERT INTO semantic_rule_slots(
              rule_type_key, slot_key, selector_type, required, slot_order, pipeline_version
            ) VALUES (?,?,?,?,?,?)
            ON CONFLICT(rule_type_key, slot_key, selector_type)
            DO UPDATE SET required=excluded.required,
                          slot_order=excluded.slot_order,
                          pipeline_version=excluded.pipeline_version
            """,
            (rule_type_key, slot_key, selector_type, required, slot_order, PIPELINE_VERSION),
        )


def _ensure_promotion_policies(conn: sqlite3.Connection) -> None:
    for predicate_key, rule_type_key, min_confidence, required_evidence_count, allow_conflict, policy_note in _SEMANTIC_PROMOTION_POLICIES:
        row = conn.execute(
            "SELECT 1 FROM semantic_predicate_vocab WHERE predicate_key = ?",
            (predicate_key,),
        ).fetchone()
        if row is None:
            continue
        conn.execute(
            """
            INSERT INTO semantic_promotion_policies(
              predicate_key, rule_type_key, min_confidence, required_evidence_count, allow_conflict, policy_note, pipeline_version
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(predicate_key)
            DO UPDATE SET rule_type_key=excluded.rule_type_key,
                          min_confidence=excluded.min_confidence,
                          required_evidence_count=excluded.required_evidence_count,
                          allow_conflict=excluded.allow_conflict,
                          policy_note=excluded.policy_note,
                          pipeline_version=excluded.pipeline_version
            """,
            (
                predicate_key,
                rule_type_key,
                min_confidence,
                required_evidence_count,
                allow_conflict,
                policy_note,
                PIPELINE_VERSION,
            ),
        )


@dataclass(frozen=True)
class EntitySeed:
    entity_kind: str
    canonical_key: str
    canonical_label: str
    actor_kind: str | None = None
    classification_tag: str | None = None
    office_kind: str | None = None
    ref_kind: str | None = None
    source_title: str | None = None
    aliases: tuple[str, ...] = ()


_ENTITY_SEEDS: tuple[EntitySeed, ...] = (
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:george_w_bush",
        canonical_label="George W. Bush",
        actor_kind="person_actor",
        aliases=("George W. Bush", "George Bush", "Bush"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:john_roberts",
        canonical_label="John Roberts",
        actor_kind="person_actor",
        aliases=("John Roberts", "Roberts"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:samuel_alito",
        canonical_label="Samuel Alito",
        actor_kind="person_actor",
        aliases=("Samuel Alito", "Alito"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:harriet_miers",
        canonical_label="Harriet Miers",
        actor_kind="person_actor",
        aliases=("Harriet Miers", "Miers"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:u_s_senate",
        canonical_label="U.S. Senate",
        actor_kind="institution_actor",
        aliases=("U.S. Senate", "US Senate", "United States Senate", "Senate"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:u_s_house_of_representatives",
        canonical_label="United States House of Representatives",
        actor_kind="institution_actor",
        aliases=("United States House of Representatives", "U.S. House of Representatives", "House of Representatives", "House"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:united_states_department_of_defense",
        canonical_label="United States Department of Defense",
        actor_kind="institution_actor",
        aliases=("Department of Defense", "Defense Department", "DoD", "United States Department of Defense"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:u_s_supreme_court",
        canonical_label="Supreme Court of the United States",
        actor_kind="institution_actor",
        classification_tag="court",
        aliases=("U.S. Supreme Court", "US Supreme Court", "United States Supreme Court", "Supreme Court"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:united_states_district_court",
        canonical_label="United States district court",
        actor_kind="institution_actor",
        classification_tag="court",
        aliases=("United States district court", "U.S. district court", "US district court", "district court"),
    ),
    EntitySeed(
        entity_kind="actor",
        canonical_key="actor:sixth_circuit",
        canonical_label="United States Court of Appeals for the Sixth Circuit",
        actor_kind="institution_actor",
        classification_tag="court",
        aliases=("United States Court of Appeals for the Sixth Circuit", "U.S. Court of Appeals for the Sixth Circuit", "Sixth Circuit", "6th Circuit"),
    ),
    EntitySeed(
        entity_kind="office",
        canonical_key="office:president_of_the_united_states",
        canonical_label="President of the United States",
        office_kind="office",
        aliases=("President of the United States", "President Bush"),
    ),
)


_PREDICATES = (
    ("nominated", "nominated", "executive_action", 1, None, "gwb_nomination_v1"),
    ("confirmed_by", "confirmed by", "legislative_action", 1, None, "gwb_confirmation_v1"),
    ("signed", "signed", "executive_action", 1, None, "gwb_signed_v1"),
    ("vetoed", "vetoed", "executive_action", 1, None, "gwb_vetoed_v1"),
    ("authorized", "authorized", "executive_action", 1, None, "gwb_authorized_v1"),
    ("ruled_by", "ruled by", "adjudicative_review", 1, None, "gwb_ruled_by_v1"),
    ("challenged_in", "challenged in", "adjudicative_review", 1, None, "gwb_challenged_in_v1"),
    ("subject_of_review_by", "subject of review by", "adjudicative_review", 1, None, "gwb_review_v1"),
    ("funded_by", "funded by", "resource_allocation", 1, None, "gwb_funded_by_v1"),
    ("sanctioned", "sanctioned", "sanction_imposition", 1, None, "gwb_sanctioned_v1"),
)


_BUSH_ADMINISTRATION_SURFACES = (
    "Bush administration",
    "the administration",
    "White House",
)

_ABSTAINED_TITLE_SURFACES = (
    "the President",
    "the court",
)


def _slug(text: str) -> str:
    parts: list[str] = []
    previous_sep = True
    for ch in text.casefold():
        if ch.isalnum():
            parts.append(ch)
            previous_sep = False
        else:
            if not previous_sep:
                parts.append("_")
            previous_sep = True
    return "".join(parts).strip("_")


def _normalize_phrase(text: str) -> str:
    return f" {' '.join(_slug(text).split('_'))} "


def _text_contains_phrase(text: str, phrase: str) -> bool:
    if not text.strip() or not phrase.strip():
        return False
    return _normalize_phrase(phrase) in _normalize_phrase(text)


def _ensure_shared_actor(
    conn: sqlite3.Connection,
    *,
    canonical_key: str,
    display_name: str,
    actor_kind: str,
    pipeline_version: str,
) -> int:
    conn.execute(
        """
        INSERT INTO actors(actor_kind, canonical_key, display_name, review_status, pipeline_version)
        VALUES (?,?,?,?,?)
        ON CONFLICT(canonical_key)
        DO UPDATE SET actor_kind=excluded.actor_kind,
                      display_name=excluded.display_name,
                      review_status=excluded.review_status,
                      pipeline_version=excluded.pipeline_version
        """,
        (actor_kind, canonical_key, display_name, "deterministic_v1", pipeline_version),
    )
    row = conn.execute("SELECT actor_id FROM actors WHERE canonical_key = ?", (canonical_key,)).fetchone()
    assert row is not None
    return int(row["actor_id"])


def _upsert_actor_alias(
    conn: sqlite3.Connection,
    *,
    actor_id: int,
    alias_text: str,
    source_kind: str,
    source_ref: str | None,
    is_primary: bool,
    pipeline_version: str,
) -> None:
    normalized_alias = _slug(alias_text)
    if not normalized_alias:
        return
    conn.execute(
        """
        INSERT INTO actor_aliases(
          actor_id, alias_text, normalized_alias, source_kind, source_ref, review_status, is_primary, pipeline_version
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(actor_id, normalized_alias, source_kind, source_ref)
        DO UPDATE SET alias_text=excluded.alias_text,
                      review_status=excluded.review_status,
                      is_primary=MAX(actor_aliases.is_primary, excluded.is_primary),
                      pipeline_version=excluded.pipeline_version
        """,
        (actor_id, alias_text, normalized_alias, source_kind, source_ref, "deterministic_v1", 1 if is_primary else 0, pipeline_version),
    )


def _upsert_seed_entity(
    conn: sqlite3.Connection,
    seed: EntitySeed,
    *,
    pipeline_version: str = PIPELINE_VERSION,
) -> int:
    conn.execute(
        """
        INSERT INTO semantic_entities(entity_kind, canonical_key, canonical_label, review_status, pipeline_version)
        VALUES (?,?,?,?,?)
        ON CONFLICT(canonical_key)
        DO UPDATE SET canonical_label=excluded.canonical_label, review_status=excluded.review_status, pipeline_version=excluded.pipeline_version
        """,
        (seed.entity_kind, seed.canonical_key, seed.canonical_label, "deterministic_v1", pipeline_version),
    )
    row = conn.execute("SELECT entity_id FROM semantic_entities WHERE canonical_key = ?", (seed.canonical_key,)).fetchone()
    assert row is not None
    entity_id = int(row["entity_id"])
    if seed.entity_kind == "actor":
        shared_actor_id = _ensure_shared_actor(
            conn,
            canonical_key=seed.canonical_key,
            display_name=seed.canonical_label,
            actor_kind=seed.actor_kind or "actor",
            pipeline_version=pipeline_version,
        )
        conn.execute(
            "UPDATE semantic_entities SET shared_actor_id = ? WHERE entity_id = ?",
            (shared_actor_id, entity_id),
        )
        conn.execute(
            """
            INSERT INTO semantic_entity_actors(entity_id, actor_kind, classification_tag)
            VALUES (?,?,?)
            ON CONFLICT(entity_id) DO UPDATE SET actor_kind=excluded.actor_kind, classification_tag=excluded.classification_tag
            """,
            (entity_id, seed.actor_kind, seed.classification_tag),
        )
        _upsert_actor_alias(
            conn,
            actor_id=shared_actor_id,
            alias_text=seed.canonical_label,
            source_kind="canonical_label",
            source_ref=seed.canonical_key,
            is_primary=True,
            pipeline_version=pipeline_version,
        )
        for alias in seed.aliases:
            _upsert_actor_alias(
                conn,
                actor_id=shared_actor_id,
                alias_text=alias,
                source_kind="seed_alias",
                source_ref=seed.canonical_key,
                is_primary=alias == seed.canonical_label,
                pipeline_version=pipeline_version,
            )
    elif seed.entity_kind == "office":
        conn.execute(
            """
            INSERT INTO semantic_entity_offices(entity_id, office_kind)
            VALUES (?,?)
            ON CONFLICT(entity_id) DO UPDATE SET office_kind=excluded.office_kind
            """,
            (entity_id, seed.office_kind or "office"),
        )
    elif seed.entity_kind == "legal_ref":
        conn.execute(
            """
            INSERT INTO semantic_entity_legal_refs(entity_id, ref_kind, source_title)
            VALUES (?,?,?)
            ON CONFLICT(entity_id) DO UPDATE SET ref_kind=excluded.ref_kind, source_title=excluded.source_title
            """,
            (entity_id, seed.ref_kind or "authority_title", seed.source_title or seed.canonical_label),
        )
    return entity_id


def _ensure_predicates(conn: sqlite3.Connection) -> dict[str, int]:
    for predicate_key, display_label, family, is_directed, inverse_key, rule_key in _PREDICATES:
        conn.execute(
            """
            INSERT INTO semantic_predicate_vocab(
              predicate_key, display_label, predicate_family, is_directed, inverse_predicate_key, promotion_rule_key, active_v1
            ) VALUES (?,?,?,?,?,?,1)
            ON CONFLICT(predicate_key)
            DO UPDATE SET display_label=excluded.display_label,
                          predicate_family=excluded.predicate_family,
                          is_directed=excluded.is_directed,
                          inverse_predicate_key=excluded.inverse_predicate_key,
                          promotion_rule_key=excluded.promotion_rule_key,
                          active_v1=excluded.active_v1
            """,
            (predicate_key, display_label, family, is_directed, inverse_key, rule_key),
        )
    _ensure_promotion_policies(conn)
    rows = conn.execute("SELECT predicate_id, predicate_key FROM semantic_predicate_vocab").fetchall()
    return {str(row["predicate_key"]): int(row["predicate_id"]) for row in rows}


def _seed_entities(conn: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for seed in _ENTITY_SEEDS:
        out[seed.canonical_key] = _upsert_seed_entity(conn, seed)
    # Explicit office holding for Bush.
    bush_id = out["actor:george_w_bush"]
    office_id = out["office:president_of_the_united_states"]
    conn.execute(
        """
        INSERT INTO semantic_office_holdings(
          person_entity_id, office_entity_id, start_date, end_date, source, pipeline_version
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(person_entity_id, office_entity_id, start_date, end_date) DO UPDATE SET source=excluded.source, pipeline_version=excluded.pipeline_version
        """,
        (bush_id, office_id, "2001-01-20", "2009-01-20", "reviewed_gwb_v1", PIPELINE_VERSION),
    )
    return out


def _delete_run_rows(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM mission_plan_receipts WHERE plan_node_id IN (SELECT plan_node_id FROM mission_plan_nodes WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_plan_deadlines WHERE plan_node_id IN (SELECT plan_node_id FROM mission_plan_nodes WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_actual_mapping_current WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_actual_mapping_receipts WHERE mapping_id IN (SELECT mapping_id FROM mission_actual_mappings WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_actual_mappings WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_plan_edges WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_plan_nodes WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_overlay_refs WHERE annotation_id IN (SELECT annotation_id FROM mission_observer_overlays WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_observer_overlays WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_evidence_refs WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_edges WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_node_owner_refs WHERE mission_id IN (SELECT mission_id FROM mission_nodes WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_node_event_refs WHERE mission_id IN (SELECT mission_id FROM mission_nodes WHERE run_id = ?)", (run_id,))
    conn.execute("DELETE FROM mission_nodes WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM mission_runs WHERE run_id = ?", (run_id,))
    conn.execute(
        """
        DELETE FROM semantic_relation_receipts
        WHERE relation_id IN (SELECT relation_id FROM semantic_relations WHERE candidate_id IN (
          SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?
        ))
        """,
        (run_id,),
    )
    conn.execute(
        """
        DELETE FROM semantic_relations
        WHERE candidate_id IN (SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?)
        """,
        (run_id,),
    )
    conn.execute(
        "DELETE FROM semantic_relation_candidate_receipts WHERE candidate_id IN (SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?)",
        (run_id,),
    )
    conn.execute("DELETE FROM semantic_relation_candidates WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM semantic_event_roles WHERE run_id = ?", (run_id,))
    conn.execute(
        """
        DELETE FROM semantic_mention_resolution_receipts
        WHERE resolution_id IN (
          SELECT resolution_id FROM semantic_mention_resolutions
          WHERE cluster_id IN (SELECT cluster_id FROM semantic_mention_clusters WHERE run_id = ?)
        )
        """,
        (run_id,),
    )
    conn.execute(
        "DELETE FROM semantic_mention_resolutions WHERE cluster_id IN (SELECT cluster_id FROM semantic_mention_clusters WHERE run_id = ?)",
        (run_id,),
    )
    conn.execute("DELETE FROM semantic_mention_clusters WHERE run_id = ?", (run_id,))


def submit_semantic_review_submission(
    conn: sqlite3.Connection,
    *,
    submission_id: str,
    source: str,
    run_id: str,
    corpus_label: str,
    event_id: str,
    relation_id: str | None,
    anchor_key: str | None,
    action_kind: str,
    proposed_payload: Mapping[str, Any],
    evidence_refs: Iterable[Mapping[str, Any]],
    operator_provenance: Mapping[str, Any],
    note: str,
    created_at: str,
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    conn.execute(
        """
        INSERT OR REPLACE INTO semantic_review_submissions(
          submission_id, source, run_id, corpus_label, event_id, relation_id, anchor_key,
          action_kind, proposed_payload_json, operator_provenance_json, note, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            submission_id,
            source,
            run_id,
            corpus_label,
            event_id,
            relation_id,
            anchor_key,
            action_kind,
            json.dumps(dict(proposed_payload), sort_keys=True),
            json.dumps(dict(operator_provenance), sort_keys=True),
            note,
            created_at,
        ),
    )
    conn.execute("DELETE FROM semantic_review_evidence_refs WHERE submission_id = ?", (submission_id,))
    for evidence_order, payload in enumerate(evidence_refs):
        conn.execute(
            """
            INSERT INTO semantic_review_evidence_refs(submission_id, evidence_order, evidence_payload_json)
            VALUES (?,?,?)
            """,
            (submission_id, evidence_order, json.dumps(dict(payload), sort_keys=True)),
        )
    return {
        "submission_id": submission_id,
        "source": source,
        "run_id": run_id,
        "event_id": event_id,
        "action_kind": action_kind,
    }


def list_semantic_review_submissions(
    conn: sqlite3.Connection,
    *,
    source: str,
    run_id: str | None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    ensure_gwb_semantic_schema(conn)
    if run_id:
        rows = conn.execute(
            """
            SELECT *
            FROM semantic_review_submissions
            WHERE source = ? AND run_id = ?
            ORDER BY datetime(created_at) DESC, submission_id DESC
            LIMIT ?
            """,
            (source, run_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM semantic_review_submissions
            WHERE source = ?
            ORDER BY datetime(created_at) DESC, submission_id DESC
            LIMIT ?
            """,
            (source, limit),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        evidence_rows = conn.execute(
            """
            SELECT evidence_payload_json
            FROM semantic_review_evidence_refs
            WHERE submission_id = ?
            ORDER BY evidence_order
            """,
            (str(row["submission_id"]),),
        ).fetchall()
        out.append(
            {
                "correction_submission_id": str(row["submission_id"]),
                "source": str(row["source"]),
                "run_id": str(row["run_id"]),
                "corpus_label": str(row["corpus_label"]),
                "event_id": str(row["event_id"]),
                "relation_id": str(row["relation_id"]) if row["relation_id"] is not None else None,
                "anchor_key": str(row["anchor_key"]) if row["anchor_key"] is not None else None,
                "action_kind": str(row["action_kind"]),
                "proposed_payload": json.loads(str(row["proposed_payload_json"])),
                "evidence_refs": [json.loads(str(item["evidence_payload_json"])) for item in evidence_rows],
                "operator_provenance": json.loads(str(row["operator_provenance_json"])),
                "created_at": str(row["created_at"]),
                "note": str(row["note"] or ""),
            }
        )
    return out


def persist_mission_observer(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    source: str,
    mission_observer: Mapping[str, Any],
    pipeline_version: str,
) -> None:
    ensure_gwb_semantic_schema(conn)
    conn.execute(
        """
        INSERT INTO mission_runs(run_id, source, pipeline_version)
        VALUES (?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET
          source=excluded.source,
          pipeline_version=excluded.pipeline_version
        """,
        (run_id, source, pipeline_version),
    )
    for node in mission_observer.get("missions", []):
        if not isinstance(node, Mapping):
            continue
        mission_id = str(node.get("missionId") or "")
        if not mission_id:
            continue
        conn.execute(
            """
            INSERT INTO mission_nodes(
              mission_id, run_id, node_kind, topic_label, normalized_topic, status, confidence, source_id, deadline
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(mission_id) DO UPDATE SET
              run_id=excluded.run_id,
              node_kind=excluded.node_kind,
              topic_label=excluded.topic_label,
              normalized_topic=excluded.normalized_topic,
              status=excluded.status,
              confidence=excluded.confidence,
              source_id=excluded.source_id,
              deadline=excluded.deadline
            """,
            (
                mission_id,
                run_id,
                str(node.get("nodeKind") or ""),
                str(node.get("topicLabel") or ""),
                str(node.get("normalizedTopic") or ""),
                str(node.get("status") or "candidate"),
                str(node.get("confidence") or "low"),
                str(node.get("sourceId") or ""),
                str(node.get("deadline") or "") or None,
            ),
        )
        for event_id in node.get("sourceEventIds", []) if isinstance(node.get("sourceEventIds"), list) else []:
            conn.execute(
                "INSERT OR IGNORE INTO mission_node_event_refs(mission_id, event_id) VALUES (?,?)",
                (mission_id, str(event_id)),
            )
        owners = node.get("owners", []) if isinstance(node.get("owners"), list) else []
        for owner_order, owner in enumerate(owners):
            if not isinstance(owner, Mapping):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO mission_node_owner_refs(mission_id, owner_order, entity_id, label)
                VALUES (?,?,?,?)
                """,
                (
                    mission_id,
                    owner_order,
                    int(owner["entityId"]) if owner.get("entityId") is not None else None,
                    str(owner.get("label") or ""),
                ),
            )
    for edge_index, edge in enumerate(mission_observer.get("followups", [])):
        if not isinstance(edge, Mapping):
            continue
        edge_id = f"followup:{run_id}:{edge_index}"
        conn.execute(
            """
            INSERT OR REPLACE INTO mission_edges(
              edge_id, run_id, edge_kind, source_node_id, target_node_id, activity_event_id, target_event_id,
              source_id, speaker, followup_topic, status, confidence, deadline, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                edge_id,
                run_id,
                "followup_resolution",
                str(edge.get("resolvedMissionId") or "") or None,
                str(edge.get("resolvedMissionId") or "") or None,
                str(edge.get("eventId") or "") or None,
                str(edge.get("targetEventId") or "") or None,
                str(edge.get("sourceId") or "") or None,
                str(edge.get("speaker") or "") or None,
                str(edge.get("followupTopic") or ""),
                str(edge.get("status") or "abstained"),
                str(edge.get("confidence") or "low"),
                str(edge.get("deadline") or "") or None,
                "",
            ),
        )
    overlays = mission_observer.get("sb_observer_overlays", [])
    if isinstance(overlays, list):
        for overlay in overlays:
            if not isinstance(overlay, Mapping):
                continue
            annotation_id = str(overlay.get("annotation_id") or "")
            if not annotation_id:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO mission_observer_overlays(
                  annotation_id, run_id, activity_event_id, sb_state_id, observer_kind, status, confidence, provenance_json, note
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    annotation_id,
                    run_id,
                    str(overlay.get("activity_event_id") or ""),
                    str(overlay.get("sb_state_id") or "") or None,
                    str(overlay.get("observer_kind") or ""),
                    str(overlay.get("status") or "candidate"),
                    str(overlay.get("confidence") or "low"),
                    json.dumps(dict(overlay.get("provenance", {})), sort_keys=True),
                    str(overlay.get("note") or ""),
                ),
            )
            for ref_group in ("mission_refs", "evidence_refs"):
                refs = overlay.get(ref_group)
                if not isinstance(refs, list):
                    continue
                for ref_order, payload in enumerate(refs):
                    if not isinstance(payload, Mapping):
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO mission_overlay_refs(annotation_id, ref_group, ref_order, ref_payload_json)
                        VALUES (?,?,?,?)
                        """,
                        (annotation_id, ref_group, ref_order, json.dumps(dict(payload), sort_keys=True)),
                    )
                    if ref_group == "evidence_refs":
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO mission_evidence_refs(run_id, owner_kind, owner_id, evidence_order, evidence_payload_json)
                            VALUES (?,?,?,?,?)
                            """,
                            (run_id, "overlay", annotation_id, ref_order, json.dumps(dict(payload), sort_keys=True)),
                        )


def load_mission_observer(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    nodes: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT mission_id, node_kind, topic_label, normalized_topic, status, confidence, source_id, deadline
        FROM mission_nodes
        WHERE run_id = ?
        ORDER BY source_id, topic_label, mission_id
        """,
        (run_id,),
    ).fetchall():
        mission_id = str(row["mission_id"])
        event_refs = [
            str(item["event_id"])
            for item in conn.execute(
                "SELECT event_id FROM mission_node_event_refs WHERE mission_id = ? ORDER BY event_id",
                (mission_id,),
            ).fetchall()
        ]
        owners = [
            {
                "entityId": int(item["entity_id"]) if item["entity_id"] is not None else None,
                "label": str(item["label"]),
            }
            for item in conn.execute(
                """
                SELECT entity_id, label
                FROM mission_node_owner_refs
                WHERE mission_id = ?
                ORDER BY owner_order
                """,
                (mission_id,),
            ).fetchall()
        ]
        nodes.append(
            {
                "missionId": mission_id,
                "nodeKind": str(row["node_kind"]),
                "topicLabel": str(row["topic_label"]),
                "normalizedTopic": str(row["normalized_topic"]),
                "status": str(row["status"]),
                "confidence": str(row["confidence"]),
                "sourceId": str(row["source_id"]),
                "sourceEventIds": event_refs,
                "deadline": str(row["deadline"]) if row["deadline"] is not None else None,
                "owners": owners,
            }
        )
    followups = [
        {
            "eventId": str(row["activity_event_id"]) if row["activity_event_id"] is not None else None,
            "sourceId": str(row["source_id"]) if row["source_id"] is not None else None,
            "speaker": str(row["speaker"]) if row["speaker"] is not None else None,
            "followupTopic": str(row["followup_topic"]),
            "resolvedMissionId": str(row["source_node_id"]) if row["source_node_id"] is not None else None,
            "resolvedTopicLabel": next((node["topicLabel"] for node in nodes if node["missionId"] == str(row["source_node_id"])), None),
            "targetEventId": str(row["target_event_id"]) if row["target_event_id"] is not None else None,
            "status": str(row["status"]),
            "confidence": str(row["confidence"]),
            "deadline": str(row["deadline"]) if row["deadline"] is not None else None,
        }
        for row in conn.execute(
            """
            SELECT source_node_id, activity_event_id, target_event_id, source_id, speaker, followup_topic, status, confidence, deadline
            FROM mission_edges
            WHERE run_id = ? AND edge_kind = 'followup_resolution'
            ORDER BY edge_id
            """,
            (run_id,),
        ).fetchall()
    ]
    overlays: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT annotation_id, activity_event_id, sb_state_id, observer_kind, status, confidence, provenance_json, note
        FROM mission_observer_overlays
        WHERE run_id = ?
        ORDER BY annotation_id
        """,
        (run_id,),
    ).fetchall():
        annotation_id = str(row["annotation_id"])
        ref_groups: dict[str, list[dict[str, Any]]] = {"mission_refs": [], "evidence_refs": []}
        for ref in conn.execute(
            """
            SELECT ref_group, ref_payload_json
            FROM mission_overlay_refs
            WHERE annotation_id = ?
            ORDER BY ref_group, ref_order
            """,
            (annotation_id,),
        ).fetchall():
            ref_groups[str(ref["ref_group"])].append(json.loads(str(ref["ref_payload_json"])))
        overlays.append(
            {
                "activity_event_id": str(row["activity_event_id"]),
                "annotation_id": annotation_id,
                "sb_state_id": str(row["sb_state_id"]) if row["sb_state_id"] is not None else None,
                "provenance": json.loads(str(row["provenance_json"])),
                "observer_kind": str(row["observer_kind"]),
                "status": str(row["status"]),
                "confidence": str(row["confidence"]),
                "mission_refs": ref_groups["mission_refs"],
                "evidence_refs": ref_groups["evidence_refs"],
                "note": str(row["note"] or ""),
            }
        )
    linked_followups = sum(1 for row in followups if row["status"] == "linked")
    return {
        "summary": {
            "mission_count": len(nodes),
            "followup_count": len(followups),
            "linked_followup_count": linked_followups,
            "abstained_followup_count": max(0, len(followups) - linked_followups),
            "overlay_count": len(overlays),
        },
        "missions": nodes,
        "followups": followups,
        "sb_observer_overlays": overlays,
        "unavailableReason": None if nodes or followups else "No explicit mission/follow-up cues were derived from this transcript/freeform run.",
    }


def _infer_deadline_semantics(raw_phrase: str | None) -> dict[str, str | None]:
    text = re.sub(r"\s+", " ", str(raw_phrase or "").strip())
    lowered = text.casefold()
    if not text:
        return {
            "raw_phrase": None,
            "due_start": None,
            "due_end": None,
            "certainty_kind": "ambiguous",
            "urgency_level": "medium",
            "flexibility_level": "flexible",
        }
    certainty_kind = "ambiguous"
    urgency_level = "medium"
    flexibility_level = "flexible"
    if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", lowered) or "sharp" in lowered:
        certainty_kind = "exact_time"
        urgency_level = "high"
        flexibility_level = "hard"
    elif "close of business" in lowered or re.search(r"\bby\s+[a-z]+day\b", lowered) or re.fullmatch(r"[A-Za-z]+", text):
        certainty_kind = "day_bound"
        urgency_level = "high"
        flexibility_level = "firm"
    elif "next week" in lowered or "sometime next week" in lowered:
        certainty_kind = "range_bound"
        urgency_level = "medium"
        flexibility_level = "soft"
    elif "next year" in lowered or "sometime next year" in lowered:
        certainty_kind = "horizon_bound"
        urgency_level = "low"
        flexibility_level = "soft"
    if "sometime" in lowered:
        flexibility_level = "soft"
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})(?:[ t](\d{2}:\d{2}(?::\d{2})?z?))?\b", text, flags=re.IGNORECASE)
    due_start: str | None = None
    due_end: str | None = None
    if iso_match:
        due_start = iso_match.group(1)
        if iso_match.group(2):
            due_start = f"{iso_match.group(1)}T{iso_match.group(2).upper().replace('Z', '')}"
            if not due_start.endswith("Z"):
                due_start = f"{due_start}Z"
        due_end = due_start
        if certainty_kind == "ambiguous":
            certainty_kind = "exact_time" if "T" in due_start else "day_bound"
    return {
        "raw_phrase": text,
        "due_start": due_start,
        "due_end": due_end,
        "certainty_kind": certainty_kind,
        "urgency_level": urgency_level,
        "flexibility_level": flexibility_level,
    }


def ensure_mission_plan_seed(conn: sqlite3.Connection, *, run_id: str) -> None:
    ensure_gwb_semantic_schema(conn)
    mission_rows = conn.execute(
        """
        SELECT mission_id, node_kind, topic_label, status, confidence, source_id, deadline
        FROM mission_nodes
        WHERE run_id = ?
        ORDER BY source_id, topic_label, mission_id
        """,
        (run_id,),
    ).fetchall()
    for row in mission_rows:
        mission_id = str(row["mission_id"])
        plan_node_id = f"plan:{mission_id}"
        conn.execute(
            """
            INSERT INTO mission_plan_nodes(
              plan_node_id, run_id, node_kind, title, status, source_kind, mission_id, parent_plan_node_id, target_weight
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(plan_node_id) DO UPDATE SET
              title=excluded.title,
              status=excluded.status,
              mission_id=excluded.mission_id,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                plan_node_id,
                run_id,
                "mission",
                str(row["topic_label"]),
                "active" if str(row["status"] or "candidate") != "obsolete" else "obsolete",
                "observer_seed",
                mission_id,
                None,
                1.0,
            ),
        )
        semantics = _infer_deadline_semantics(str(row["deadline"] or "") or None)
        if semantics["raw_phrase"] is not None:
            conn.execute(
                """
                INSERT INTO mission_plan_deadlines(
                  plan_node_id, raw_phrase, due_start, due_end, certainty_kind, urgency_level, flexibility_level
                ) VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(plan_node_id) DO UPDATE SET
                  raw_phrase=excluded.raw_phrase,
                  due_start=excluded.due_start,
                  due_end=excluded.due_end,
                  certainty_kind=excluded.certainty_kind,
                  urgency_level=excluded.urgency_level,
                  flexibility_level=excluded.flexibility_level
                """,
                (
                    plan_node_id,
                    semantics["raw_phrase"],
                    semantics["due_start"],
                    semantics["due_end"],
                    semantics["certainty_kind"],
                    semantics["urgency_level"],
                    semantics["flexibility_level"],
                ),
            )
        receipts = [
            ("source_kind", "observer_seed"),
            ("mission_id", mission_id),
            ("confidence", str(row["confidence"] or "")),
            ("source_id", str(row["source_id"] or "")),
        ]
        conn.execute("DELETE FROM mission_plan_receipts WHERE plan_node_id = ?", (plan_node_id,))
        for receipt_order, (kind, value) in enumerate(receipts):
            conn.execute(
                """
                INSERT INTO mission_plan_receipts(plan_node_id, receipt_order, receipt_kind, receipt_value)
                VALUES (?,?,?,?)
                """,
                (plan_node_id, receipt_order, kind, value),
            )


def upsert_mission_plan_node(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    plan_node_id: str,
    node_kind: str,
    title: str,
    status: str,
    source_kind: str,
    mission_id: str | None,
    parent_plan_node_id: str | None,
    target_weight: float,
    raw_phrase: str | None,
    due_start: str | None,
    due_end: str | None,
    certainty_kind: str | None,
    urgency_level: str | None,
    flexibility_level: str | None,
    receipts: Iterable[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    conn.execute(
        """
        INSERT INTO mission_plan_nodes(
          plan_node_id, run_id, node_kind, title, status, source_kind, mission_id, parent_plan_node_id, target_weight
        ) VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(plan_node_id) DO UPDATE SET
          node_kind=excluded.node_kind,
          title=excluded.title,
          status=excluded.status,
          source_kind=excluded.source_kind,
          mission_id=excluded.mission_id,
          parent_plan_node_id=excluded.parent_plan_node_id,
          target_weight=excluded.target_weight,
          updated_at=CURRENT_TIMESTAMP
        """,
        (plan_node_id, run_id, node_kind, title, status, source_kind, mission_id, parent_plan_node_id, target_weight),
    )
    if parent_plan_node_id:
        edge_id = f"edge:contains:{parent_plan_node_id}:{plan_node_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO mission_plan_edges(edge_id, run_id, from_plan_node_id, to_plan_node_id, edge_kind)
            VALUES (?,?,?,?,?)
            """,
            (edge_id, run_id, parent_plan_node_id, plan_node_id, "contains"),
        )
    semantics = {
        "raw_phrase": raw_phrase,
        "due_start": due_start,
        "due_end": due_end,
        "certainty_kind": certainty_kind,
        "urgency_level": urgency_level,
        "flexibility_level": flexibility_level,
    }
    if not semantics["certainty_kind"] and raw_phrase:
        semantics.update(_infer_deadline_semantics(raw_phrase))
    if semantics["raw_phrase"] or semantics["due_start"] or semantics["due_end"]:
        conn.execute(
            """
            INSERT INTO mission_plan_deadlines(
              plan_node_id, raw_phrase, due_start, due_end, certainty_kind, urgency_level, flexibility_level
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(plan_node_id) DO UPDATE SET
              raw_phrase=excluded.raw_phrase,
              due_start=excluded.due_start,
              due_end=excluded.due_end,
              certainty_kind=excluded.certainty_kind,
              urgency_level=excluded.urgency_level,
              flexibility_level=excluded.flexibility_level
            """,
            (
                plan_node_id,
                semantics["raw_phrase"],
                semantics["due_start"],
                semantics["due_end"],
                semantics["certainty_kind"] or "ambiguous",
                semantics["urgency_level"] or "medium",
                semantics["flexibility_level"] or "flexible",
            ),
        )
    conn.execute("DELETE FROM mission_plan_receipts WHERE plan_node_id = ?", (plan_node_id,))
    if receipts:
        for receipt_order, (kind, value) in enumerate(receipts):
            conn.execute(
                """
                INSERT INTO mission_plan_receipts(plan_node_id, receipt_order, receipt_kind, receipt_value)
                VALUES (?,?,?,?)
                """,
                (plan_node_id, receipt_order, kind, value),
            )
    return {"plan_node_id": plan_node_id, "run_id": run_id, "title": title, "node_kind": node_kind}


def load_mission_plan(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_mission_plan_seed(conn, run_id=run_id)
    nodes: list[dict[str, Any]] = []
    for row in conn.execute(
        """
        SELECT n.plan_node_id, n.node_kind, n.title, n.status, n.source_kind, n.mission_id, n.parent_plan_node_id, n.target_weight,
               d.raw_phrase, d.due_start, d.due_end, d.certainty_kind, d.urgency_level, d.flexibility_level
        FROM mission_plan_nodes AS n
        LEFT JOIN mission_plan_deadlines AS d ON d.plan_node_id = n.plan_node_id
        WHERE n.run_id = ?
        ORDER BY n.node_kind, n.title, n.plan_node_id
        """,
        (run_id,),
    ).fetchall():
        receipts = [
            {"kind": str(item["receipt_kind"]), "value": str(item["receipt_value"])}
            for item in conn.execute(
                """
                SELECT receipt_kind, receipt_value
                FROM mission_plan_receipts
                WHERE plan_node_id = ?
                ORDER BY receipt_order
                """,
                (str(row["plan_node_id"]),),
            ).fetchall()
        ]
        nodes.append(
            {
                "planNodeId": str(row["plan_node_id"]),
                "nodeKind": str(row["node_kind"]),
                "title": str(row["title"]),
                "status": str(row["status"]),
                "sourceKind": str(row["source_kind"]),
                "missionId": str(row["mission_id"]) if row["mission_id"] is not None else None,
                "parentPlanNodeId": str(row["parent_plan_node_id"]) if row["parent_plan_node_id"] is not None else None,
                "targetWeight": float(row["target_weight"]),
                "deadline": {
                    "rawPhrase": str(row["raw_phrase"]) if row["raw_phrase"] is not None else None,
                    "dueStart": str(row["due_start"]) if row["due_start"] is not None else None,
                    "dueEnd": str(row["due_end"]) if row["due_end"] is not None else None,
                    "certaintyKind": str(row["certainty_kind"]) if row["certainty_kind"] is not None else "ambiguous",
                    "urgencyLevel": str(row["urgency_level"]) if row["urgency_level"] is not None else "medium",
                    "flexibilityLevel": str(row["flexibility_level"]) if row["flexibility_level"] is not None else "flexible",
                },
                "receipts": receipts,
            }
        )
    edges = [
        {
            "edgeId": str(row["edge_id"]),
            "fromPlanNodeId": str(row["from_plan_node_id"]),
            "toPlanNodeId": str(row["to_plan_node_id"]),
            "edgeKind": str(row["edge_kind"]),
        }
        for row in conn.execute(
            """
            SELECT edge_id, from_plan_node_id, to_plan_node_id, edge_kind
            FROM mission_plan_edges
            WHERE run_id = ?
            ORDER BY edge_kind, edge_id
            """,
            (run_id,),
        ).fetchall()
    ]
    return {"nodes": nodes, "edges": edges}


def upsert_mission_actual_mapping(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    mapping_id: str,
    activity_ref_id: str,
    plan_node_id: str | None,
    mapping_kind: str = "reviewed_link",
    status: str = "linked",
    confidence_tier: str = "high",
    note: str = "",
    receipts: Iterable[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    normalized_plan_node_id = str(plan_node_id or "") or None
    conn.execute(
        """
        INSERT INTO mission_actual_mappings(
          mapping_id, run_id, activity_ref_id, plan_node_id, mapping_kind, status, confidence_tier, note
        ) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(mapping_id) DO UPDATE SET
          activity_ref_id=excluded.activity_ref_id,
          plan_node_id=excluded.plan_node_id,
          mapping_kind=excluded.mapping_kind,
          status=excluded.status,
          confidence_tier=excluded.confidence_tier,
          note=excluded.note
        """,
        (mapping_id, run_id, activity_ref_id, normalized_plan_node_id, mapping_kind, status, confidence_tier, note),
    )
    conn.execute("DELETE FROM mission_actual_mapping_receipts WHERE mapping_id = ?", (mapping_id,))
    if receipts:
        for receipt_order, (kind, value) in enumerate(receipts):
            conn.execute(
                """
                INSERT INTO mission_actual_mapping_receipts(mapping_id, receipt_order, receipt_kind, receipt_value)
                VALUES (?,?,?,?)
                """,
                (mapping_id, receipt_order, kind, value),
            )
    _refresh_mission_actual_mapping_current(conn, run_id=run_id, activity_ref_id=activity_ref_id)
    return {
        "mapping_id": mapping_id,
        "run_id": run_id,
        "activity_ref_id": activity_ref_id,
        "plan_node_id": normalized_plan_node_id,
        "mapping_kind": mapping_kind,
        "status": status,
        "confidence_tier": confidence_tier,
        "note": note,
    }


def _refresh_mission_actual_mapping_current(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    activity_ref_id: str,
) -> None:
    ensure_gwb_semantic_schema(conn)
    row = conn.execute(
        """
        SELECT mapping_id, plan_node_id, mapping_kind, status, confidence_tier, note
        FROM mission_actual_mappings
        WHERE run_id = ? AND activity_ref_id = ?
        ORDER BY datetime(created_at) DESC, mapping_id DESC
        LIMIT 1
        """,
        (run_id, activity_ref_id),
    ).fetchone()
    if row is None:
        conn.execute(
            "DELETE FROM mission_actual_mapping_current WHERE run_id = ? AND activity_ref_id = ?",
            (run_id, activity_ref_id),
        )
        return
    conn.execute(
        """
        INSERT INTO mission_actual_mapping_current(
          run_id, activity_ref_id, mapping_id, plan_node_id, mapping_kind, status, confidence_tier, note, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(run_id, activity_ref_id) DO UPDATE SET
          mapping_id=excluded.mapping_id,
          plan_node_id=excluded.plan_node_id,
          mapping_kind=excluded.mapping_kind,
          status=excluded.status,
          confidence_tier=excluded.confidence_tier,
          note=excluded.note,
          updated_at=CURRENT_TIMESTAMP
        """,
        (
            run_id,
            activity_ref_id,
            str(row["mapping_id"]),
            str(row["plan_node_id"] or "") or None,
            str(row["mapping_kind"]),
            str(row["status"]),
            str(row["confidence_tier"]),
            str(row["note"]),
        ),
    )


def _refresh_all_mission_actual_mapping_current(conn: sqlite3.Connection, *, run_id: str) -> None:
    ensure_gwb_semantic_schema(conn)
    activity_ref_ids = [
        str(row["activity_ref_id"])
        for row in conn.execute(
            "SELECT DISTINCT activity_ref_id FROM mission_actual_mappings WHERE run_id = ? ORDER BY activity_ref_id",
            (run_id,),
        ).fetchall()
    ]
    conn.execute("DELETE FROM mission_actual_mapping_current WHERE run_id = ?", (run_id,))
    for activity_ref_id in activity_ref_ids:
        _refresh_mission_actual_mapping_current(conn, run_id=run_id, activity_ref_id=activity_ref_id)


def load_mission_actual_mappings(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    ensure_gwb_semantic_schema(conn)
    rows = conn.execute(
        """
        SELECT mapping_id, activity_ref_id, plan_node_id, mapping_kind, status, confidence_tier, note, created_at
        FROM mission_actual_mappings
        WHERE run_id = ?
        ORDER BY datetime(created_at) DESC, mapping_id DESC
        """,
        (run_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        receipts = [
            {"kind": str(item["receipt_kind"]), "value": str(item["receipt_value"])}
            for item in conn.execute(
                """
                SELECT receipt_kind, receipt_value
                FROM mission_actual_mapping_receipts
                WHERE mapping_id = ?
                ORDER BY receipt_order
                """,
                (str(row["mapping_id"]),),
            ).fetchall()
        ]
        out.append(
            {
                "mappingId": str(row["mapping_id"]),
                "activityRefId": str(row["activity_ref_id"]),
                "planNodeId": str(row["plan_node_id"] or "") or None,
                "mappingKind": str(row["mapping_kind"]),
                "status": str(row["status"]),
                "confidenceTier": str(row["confidence_tier"]),
                "note": str(row["note"]),
                "createdAt": str(row["created_at"]),
                "receipts": receipts,
            }
        )
    return out


def load_mission_actual_mapping_current(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    ensure_gwb_semantic_schema(conn)
    history_count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM mission_actual_mappings WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    current_count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM mission_actual_mapping_current WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if int(history_count_row["n"] or 0) > 0 and int(current_count_row["n"] or 0) == 0:
        _refresh_all_mission_actual_mapping_current(conn, run_id=run_id)
    rows = conn.execute(
        """
        SELECT run_id, activity_ref_id, mapping_id, plan_node_id, mapping_kind, status, confidence_tier, note, updated_at
        FROM mission_actual_mapping_current
        WHERE run_id = ?
        ORDER BY activity_ref_id
        """,
        (run_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        receipts = [
            {"kind": str(item["receipt_kind"]), "value": str(item["receipt_value"])}
            for item in conn.execute(
                """
                SELECT receipt_kind, receipt_value
                FROM mission_actual_mapping_receipts
                WHERE mapping_id = ?
                ORDER BY receipt_order
                """,
                (str(row["mapping_id"]),),
            ).fetchall()
        ]
        out.append(
            {
                "runId": str(row["run_id"]),
                "activityRefId": str(row["activity_ref_id"]),
                "mappingId": str(row["mapping_id"]),
                "planNodeId": str(row["plan_node_id"] or "") or None,
                "mappingKind": str(row["mapping_kind"]),
                "status": str(row["status"]),
                "confidenceTier": str(row["confidence_tier"]),
                "note": str(row["note"]),
                "updatedAt": str(row["updated_at"]),
                "receipts": receipts,
            }
        )
    return out


def _event_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    return {
        str(event.get("event_id")): event
        for event in events
        if isinstance(event, Mapping) and event.get("event_id")
    }


def _build_seed_index(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for seed in _ENTITY_SEEDS:
        if seed.entity_kind == "actor":
            rows = conn.execute(
                """
                SELECT aa.alias_text
                FROM actor_aliases AS aa
                JOIN actors AS a ON a.actor_id = aa.actor_id
                WHERE a.canonical_key = ?
                ORDER BY aa.is_primary DESC, aa.alias_text
                """,
                (seed.canonical_key,),
            ).fetchall()
            if rows:
                out[seed.canonical_key] = [str(row["alias_text"]) for row in rows]
                continue
        out[seed.canonical_key] = list(seed.aliases)
    # Add reviewed legal refs from the current GWB linkage seed.
    rows = conn.execute(
        """
        SELECT DISTINCT authority_title
        FROM gwb_us_law_linkage_seed_authorities
        ORDER BY authority_title
        """
    ).fetchall()
    for row in rows:
        title = str(row["authority_title"])
        canonical_key = f"legal_ref:{_slug(title)}"
        out[canonical_key] = [title]
    return out


def _ensure_legal_ref_entity(conn: sqlite3.Connection, title: str) -> int:
    seed = EntitySeed(
        entity_kind="legal_ref",
        canonical_key=f"legal_ref:{_slug(title)}",
        canonical_label=title,
        ref_kind="authority_title",
        source_title=title,
        aliases=(title,),
    )
    return _upsert_seed_entity(conn, seed)


def _insert_cluster_and_resolution(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    mention_kind: str,
    canonical_key_hint: str | None,
    surface_text: str,
    source_rule: str,
    resolved_entity_id: int | None,
    resolution_status: str,
    resolution_rule: str,
    receipts: Iterable[tuple[str, str]],
    pipeline_version: str = PIPELINE_VERSION,
) -> tuple[int, int]:
    normalized_surface = _slug(surface_text)
    cur = conn.execute(
        """
        INSERT INTO semantic_mention_clusters(
          run_id, event_id, mention_kind, canonical_key_hint, surface_text, normalized_surface, source_rule
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (run_id, event_id, mention_kind, canonical_key_hint, surface_text, normalized_surface, source_rule),
    )
    cluster_id = int(cur.lastrowid)
    res_cur = conn.execute(
        """
        INSERT INTO semantic_mention_resolutions(
          cluster_id, resolved_entity_id, resolution_status, resolution_rule, pipeline_version
        ) VALUES (?,?,?,?,?)
        """,
        (cluster_id, resolved_entity_id, resolution_status, resolution_rule, pipeline_version),
    )
    resolution_id = int(res_cur.lastrowid)
    for idx, (kind, value) in enumerate(receipts, start=1):
        conn.execute(
            """
            INSERT INTO semantic_mention_resolution_receipts(resolution_id, receipt_order, reason_kind, reason_value)
            VALUES (?,?,?,?)
            """,
            (resolution_id, idx, kind, value),
        )
    return cluster_id, resolution_id


def _detect_mentions_for_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    event: Mapping[str, Any],
    entity_ids: Mapping[str, int],
) -> dict[str, list[int]]:
    text = str(event.get("text") or "")
    found: dict[str, list[int]] = defaultdict(list)
    seed_index = _build_seed_index(conn)
    # Explicit abstention surfaces first.
    for surface in _BUSH_ADMINISTRATION_SURFACES:
        if _text_contains_phrase(text, surface):
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=None,
                surface_text=surface,
                source_rule="administration_surface_v1",
                resolved_entity_id=None,
                resolution_status="abstained",
                resolution_rule="administration_noncanonical_v1",
                receipts=[("surface", surface), ("reason", "administration_discourse_label")],
            )
            found["abstained"].append(cluster_id)
    for surface in _ABSTAINED_TITLE_SURFACES:
        if _text_contains_phrase(text, surface):
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=None,
                surface_text=surface,
                source_rule="ambiguous_title_surface_v1",
                resolved_entity_id=None,
                resolution_status="abstained",
                resolution_rule="title_requires_stronger_context_v1",
                receipts=[("surface", surface), ("reason", "ambiguous_title_reference")],
            )
            found["abstained"].append(cluster_id)

    for seed in _ENTITY_SEEDS:
        for alias in seed_index.get(seed.canonical_key, list(seed.aliases)):
            if not _text_contains_phrase(text, alias):
                continue
            if seed.canonical_key == "actor:george_w_bush" and alias == "Bush" and _text_contains_phrase(text, "Bush administration"):
                continue
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor" if seed.entity_kind == "actor" else seed.entity_kind,
                canonical_key_hint=seed.canonical_key,
                surface_text=alias,
                source_rule="seed_alias_v1",
                resolved_entity_id=entity_ids[seed.canonical_key],
                resolution_status="resolved",
                resolution_rule="seed_alias_exact_v1",
                receipts=[("alias", alias), ("canonical_key", seed.canonical_key)],
            )
            found[seed.canonical_key].append(cluster_id)

    linkage_rows = conn.execute(
        """
        SELECT DISTINCT r.reason_value
        FROM gwb_us_law_linkage_match_receipts AS r
        JOIN gwb_us_law_linkage_matches AS m
          ON m.run_id = r.run_id AND m.event_id = r.event_id AND m.seed_id = r.seed_id
        WHERE r.run_id = ? AND r.event_id = ? AND r.reason_kind = 'authority_title'
        """,
        (run_id, event_id),
    ).fetchall()
    for row in linkage_rows:
        title = str(row["reason_value"])
        entity_id = _ensure_legal_ref_entity(conn, title)
        canonical_key = f"legal_ref:{_slug(title)}"
        cluster_id, _ = _insert_cluster_and_resolution(
            conn,
            run_id=run_id,
            event_id=event_id,
            mention_kind="legal_ref",
            canonical_key_hint=canonical_key,
            surface_text=title,
            source_rule="linkage_authority_title_v1",
            resolved_entity_id=entity_id,
            resolution_status="resolved",
            resolution_rule="authority_title_receipt_v1",
            receipts=[("authority_title", title)],
        )
        found[canonical_key].append(cluster_id)
    return found


def _entity_for_key(conn: sqlite3.Connection, canonical_key: str) -> int | None:
    row = conn.execute("SELECT entity_id FROM semantic_entities WHERE canonical_key = ?", (canonical_key,)).fetchone()
    return int(row["entity_id"]) if row else None


def _candidate_exists(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    predicate_id: int,
    object_entity_id: int,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM semantic_relation_candidates
        WHERE run_id = ? AND event_id = ? AND predicate_id = ? AND object_entity_id = ?
        LIMIT 1
        """,
        (run_id, event_id, predicate_id, object_entity_id),
    ).fetchone()
    return row is not None


def _load_event_linkage_matches(conn: sqlite3.Connection, *, run_id: str, event_id: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.seed_id, m.confidence, m.matched, r.reason_kind, r.reason_value
        FROM gwb_us_law_linkage_matches AS m
        LEFT JOIN gwb_us_law_linkage_match_receipts AS r
          ON r.run_id = m.run_id AND r.event_id = m.event_id AND r.seed_id = m.seed_id
        WHERE m.run_id = ? AND m.event_id = ?
        ORDER BY m.seed_id, r.receipt_order
        """,
        (run_id, event_id),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        seed_id = str(row["seed_id"])
        bucket = out.setdefault(
            seed_id,
            {
                "seed_id": seed_id,
                "confidence": str(row["confidence"] or ""),
                "matched": bool(row["matched"]),
                "receipts": [],
            },
        )
        if row["reason_kind"] is not None:
            bucket["receipts"].append((str(row["reason_kind"]), str(row["reason_value"])))
    return out


def _broader_source_seed_backfill_allowed(event: Mapping[str, Any]) -> bool:
    source_id = str(event.get("source_id") or "")
    return source_id in {"gwb_public_bios_web", "gwb_corpus_local"}


def _insert_broader_source_seed_backfill_candidates(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    event: Mapping[str, Any],
    mention_clusters: Mapping[str, list[int]],
    entity_ids: Mapping[str, int],
    predicate_ids: Mapping[str, int],
) -> None:
    if not _broader_source_seed_backfill_allowed(event):
        return

    text = str(event.get("text") or "")
    text_fold = text.casefold()
    bush_id = entity_ids.get("actor:george_w_bush")
    if bush_id is None:
        return

    linkage_matches = _load_event_linkage_matches(conn, run_id=run_id, event_id=event_id)

    iraq_match = linkage_matches.get("gwb_us_law:iraq_2002_authorization")
    if iraq_match and iraq_match["matched"] and any(term in text_fold for term in ("authorization", "authorize", "authorized")):
        legal_title = "Authorization for Use of Military Force Against Iraq Resolution of 2002"
        legal_key = f"legal_ref:{_slug(legal_title)}"
        legal_id = entity_ids.get(legal_key) or _entity_for_key(conn, legal_key) or _ensure_legal_ref_entity(conn, legal_title)
        if not _candidate_exists(
            conn,
            run_id=run_id,
            event_id=event_id,
            predicate_id=predicate_ids["authorized"],
            object_entity_id=legal_id,
        ):
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="agent", entity_id=bush_id, note="authorized_seed_backfill_v1")
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="theme", entity_id=legal_id, note="authorized_seed_backfill_v1")
            receipts = [("subject", "George W. Bush"), ("verb", "authorization"), ("cue_surface", "Iraq")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=bush_id,
                predicate_id=predicate_ids["authorized"],
                object_entity_id=legal_id,
                confidence_tier="low",
                receipts=receipts,
            )

    supreme_court_match = linkage_matches.get("gwb_us_law:supreme_court_appointments")
    supreme_court_id = entity_ids.get("actor:u_s_supreme_court") or _entity_for_key(conn, "actor:u_s_supreme_court")
    if (
        supreme_court_match
        and supreme_court_id is not None
        and mention_clusters.get("actor:u_s_supreme_court")
        and any(term in text_fold for term in ("supreme court", "court decision", "ordered", "recount"))
    ):
        if not _candidate_exists(
            conn,
            run_id=run_id,
            event_id=event_id,
            predicate_id=predicate_ids["subject_of_review_by"],
            object_entity_id=supreme_court_id,
        ):
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="forum", entity_id=supreme_court_id, note="subject_of_review_seed_backfill_v1")
            receipts = [("subject", "George W. Bush"), ("verb", "decision"), ("cue_surface", "Supreme Court")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=bush_id,
                predicate_id=predicate_ids["subject_of_review_by"],
                object_entity_id=supreme_court_id,
                confidence_tier="low",
                receipts=receipts,
            )


def _confidence_rank(confidence_tier: str) -> int:
    return {
        "abstain": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }.get(confidence_tier, 0)


def _load_promotion_policy_for_predicate_id(conn: sqlite3.Connection, predicate_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.predicate_key, p.promotion_rule_key, sp.rule_type_key,
               sp.min_confidence, sp.required_evidence_count, sp.allow_conflict
        FROM semantic_predicate_vocab AS p
        LEFT JOIN semantic_promotion_policies AS sp
          ON sp.predicate_key = p.predicate_key
        WHERE p.predicate_id = ?
        """,
        (predicate_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "predicate_key": str(row["predicate_key"]),
        "promotion_rule_key": str(row["promotion_rule_key"]),
        "rule_type_key": str(row["rule_type_key"]) if row["rule_type_key"] is not None else None,
        "min_confidence": str(row["min_confidence"]) if row["min_confidence"] is not None else None,
        "required_evidence_count": int(row["required_evidence_count"]) if row["required_evidence_count"] is not None else None,
        "allow_conflict": int(row["allow_conflict"]) if row["allow_conflict"] is not None else 0,
    }


def _load_promotion_policy_for_predicate_key(conn: sqlite3.Connection, predicate_key: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT p.predicate_key, p.promotion_rule_key, sp.rule_type_key,
               sp.min_confidence, sp.required_evidence_count, sp.allow_conflict
        FROM semantic_predicate_vocab AS p
        LEFT JOIN semantic_promotion_policies AS sp
          ON sp.predicate_key = p.predicate_key
        WHERE p.predicate_key = ?
        """,
        (predicate_key,),
    ).fetchone()
    if row is None:
        return None
    return {
        "predicate_key": str(row["predicate_key"]),
        "promotion_rule_key": str(row["promotion_rule_key"]),
        "rule_type_key": str(row["rule_type_key"]) if row["rule_type_key"] is not None else None,
        "min_confidence": str(row["min_confidence"]) if row["min_confidence"] is not None else None,
        "required_evidence_count": int(row["required_evidence_count"]) if row["required_evidence_count"] is not None else None,
        "allow_conflict": int(row["allow_conflict"]) if row["allow_conflict"] is not None else 0,
    }


def _policy_adjusted_confidence(
    conn: sqlite3.Connection,
    *,
    predicate_key: str,
    receipts: list[tuple[str, str]],
    legacy_confidence: str,
) -> str:
    if legacy_confidence == "abstain":
        return "abstain"
    policy = _load_promotion_policy_for_predicate_key(conn, predicate_key)
    if policy is None:
        return legacy_confidence
    required_evidence_count = policy["required_evidence_count"]
    if required_evidence_count is None:
        return legacy_confidence
    evidence_count = len({kind for kind, _ in receipts})
    if evidence_count < max(1, required_evidence_count - 1):
        return "abstain"
    if evidence_count < required_evidence_count and _confidence_rank(legacy_confidence) > _confidence_rank("low"):
        return "low"
    return legacy_confidence


def _promotion_status_from_policy(
    *,
    confidence_tier: str,
    evidence_count: int,
    min_confidence: str | None,
    required_evidence_count: int | None,
) -> str:
    if confidence_tier == "abstain":
        return "abstained"
    if required_evidence_count is not None and evidence_count < required_evidence_count:
        return "candidate"
    if min_confidence is not None and _confidence_rank(confidence_tier) < _confidence_rank(min_confidence):
        return "candidate"
    return "promoted"


def _predicate_confidence(conn: sqlite3.Connection, predicate_key: str, receipts: list[tuple[str, str]]) -> str:
    kinds = {kind for kind, _ in receipts}
    if predicate_key in {"signed", "vetoed"} and {"subject", "object_legal_ref", "verb"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="high")
    if predicate_key in {"nominated", "confirmed_by"} and {"subject", "object_actor", "verb"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="high")
    if {"subject", "verb"} <= kinds:
        return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="medium")
    return _policy_adjusted_confidence(conn, predicate_key=predicate_key, receipts=receipts, legacy_confidence="abstain")


def _insert_event_role(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    role_kind: str,
    entity_id: int | None = None,
    cluster_id: int | None = None,
    note: str | None = None,
) -> None:
    _ensure_event_role_vocab_entry(conn, role_kind)
    conn.execute(
        """
        INSERT INTO semantic_event_roles(run_id, event_id, role_kind, entity_id, cluster_id, note)
        VALUES (?,?,?,?,?,?)
        """,
        (run_id, event_id, role_kind, entity_id, cluster_id, note),
    )


def _insert_relation_candidate(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    subject_entity_id: int,
    predicate_id: int,
    object_entity_id: int,
    confidence_tier: str,
    receipts: list[tuple[str, str]],
    pipeline_version: str = PIPELINE_VERSION,
) -> int:
    policy = _load_promotion_policy_for_predicate_id(conn, predicate_id)
    evidence_count = len({kind for kind, _ in receipts})
    promotion_status = (
        _promotion_status_from_policy(
            confidence_tier=confidence_tier,
            evidence_count=evidence_count,
            min_confidence=policy["min_confidence"] if policy else None,
            required_evidence_count=policy["required_evidence_count"] if policy else None,
        )
        if policy
        else ("promoted" if confidence_tier in {"high", "medium"} else ("candidate" if confidence_tier == "low" else "abstained"))
    )
    stored_receipts = list(receipts)
    if policy is not None:
        if policy["rule_type_key"]:
            stored_receipts.append(("rule_type", str(policy["rule_type_key"])))
        stored_receipts.append(("promotion_rule_key", str(policy["promotion_rule_key"])))
        if policy["min_confidence"] is not None:
            stored_receipts.append(("promotion_min_confidence", str(policy["min_confidence"])))
        if policy["required_evidence_count"] is not None:
            stored_receipts.append(("promotion_required_evidence_count", str(policy["required_evidence_count"])))
    stored_receipts.append(("evidence_count", str(evidence_count)))
    stored_receipts.append(("promotion_status", promotion_status))
    cur = conn.execute(
        """
        INSERT INTO semantic_relation_candidates(
          run_id, event_id, subject_entity_id, predicate_id, object_entity_id, promotion_status, confidence_tier, pipeline_version
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            event_id,
            subject_entity_id,
            predicate_id,
            object_entity_id,
            promotion_status,
            confidence_tier,
            pipeline_version,
        ),
    )
    candidate_id = int(cur.lastrowid)
    for idx, (kind, value) in enumerate(stored_receipts, start=1):
        conn.execute(
            """
            INSERT INTO semantic_relation_candidate_receipts(candidate_id, receipt_order, reason_kind, reason_value)
            VALUES (?,?,?,?)
            """,
            (candidate_id, idx, kind, value),
        )
    if promotion_status == "promoted":
        rel_cur = conn.execute(
            """
            INSERT INTO semantic_relations(
              candidate_id, subject_entity_id, predicate_id, object_entity_id, event_id, confidence_tier, pipeline_version
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (candidate_id, subject_entity_id, predicate_id, object_entity_id, event_id, confidence_tier, pipeline_version),
        )
        relation_id = int(rel_cur.lastrowid)
        for idx, (kind, value) in enumerate(stored_receipts, start=1):
            conn.execute(
                """
                INSERT INTO semantic_relation_receipts(relation_id, receipt_order, reason_kind, reason_value)
                VALUES (?,?,?,?)
                """,
                (relation_id, idx, kind, value),
            )
    return candidate_id


def _extract_event_relations(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    event: Mapping[str, Any],
    mention_clusters: Mapping[str, list[int]],
    entity_ids: Mapping[str, int],
    predicate_ids: Mapping[str, int],
) -> None:
    text = str(event.get("text") or "")
    text_fold = text.casefold()

    bush_id = entity_ids.get("actor:george_w_bush")
    senate_id = entity_ids.get("actor:u_s_senate")
    legal_ref_keys = [key for key in mention_clusters if key.startswith("legal_ref:")]
    court_keys = [
        key
        for key in ("actor:u_s_supreme_court", "actor:united_states_district_court", "actor:sixth_circuit")
        if mention_clusters.get(key)
    ]
    nominee_keys = [
        key
        for key in ("actor:john_roberts", "actor:samuel_alito", "actor:harriet_miers")
        if mention_clusters.get(key)
    ]

    if bush_id and legal_ref_keys and "signed" in text_fold:
        for legal_key in legal_ref_keys:
            legal_id = entity_ids.get(legal_key) or _entity_for_key(conn, legal_key)
            if legal_id is None:
                continue
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="agent", entity_id=bush_id, note="signed_v1")
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="theme", entity_id=legal_id, note="signed_v1")
            receipts = [("subject", "George W. Bush"), ("verb", "signed"), ("object_legal_ref", legal_key)]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=bush_id,
                predicate_id=predicate_ids["signed"],
                object_entity_id=legal_id,
                confidence_tier=_predicate_confidence(conn, "signed", receipts),
                receipts=receipts,
            )

    if bush_id and legal_ref_keys and "veto" in text_fold:
        for legal_key in legal_ref_keys:
            legal_id = entity_ids.get(legal_key) or _entity_for_key(conn, legal_key)
            if legal_id is None:
                continue
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="agent", entity_id=bush_id, note="vetoed_v1")
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="theme", entity_id=legal_id, note="vetoed_v1")
            receipts = [("subject", "George W. Bush"), ("verb", "veto"), ("object_legal_ref", legal_key)]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=bush_id,
                predicate_id=predicate_ids["vetoed"],
                object_entity_id=legal_id,
                confidence_tier=_predicate_confidence(conn, "vetoed", receipts),
                receipts=receipts,
            )

    if bush_id and nominee_keys and "nominat" in text_fold:
        for nominee_key in nominee_keys:
            nominee_id = entity_ids[nominee_key]
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="agent", entity_id=bush_id, note="nominated_v1")
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="patient", entity_id=nominee_id, note="nominated_v1")
            receipts = [("subject", "George W. Bush"), ("verb", "nominated"), ("object_actor", nominee_key)]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=bush_id,
                predicate_id=predicate_ids["nominated"],
                object_entity_id=nominee_id,
                confidence_tier=_predicate_confidence(conn, "nominated", receipts),
                receipts=receipts,
            )

    if senate_id and nominee_keys and ("confirmed by the senate" in text_fold or "confirmed by senate" in text_fold or "confirmed the senate" in text_fold):
        for nominee_key in nominee_keys:
            nominee_id = entity_ids[nominee_key]
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="patient", entity_id=nominee_id, note="confirmed_by_v1")
            _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="authority", entity_id=senate_id, note="confirmed_by_v1")
            receipts = [("subject", nominee_key), ("verb", "confirmed_by"), ("object_actor", "actor:u_s_senate")]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=nominee_id,
                predicate_id=predicate_ids["confirmed_by"],
                object_entity_id=senate_id,
                confidence_tier=_predicate_confidence(conn, "confirmed_by", receipts),
                receipts=receipts,
            )

    review_subject_keys = legal_ref_keys if legal_ref_keys else (["actor:george_w_bush"] if bush_id is not None else [])
    review_court_ids = [entity_ids.get(key) or _entity_for_key(conn, key) for key in court_keys]
    review_court_ids = [cid for cid in review_court_ids if cid is not None]
    if review_subject_keys and review_court_ids:
        for subject_key in review_subject_keys:
            subject_id = entity_ids.get(subject_key) or _entity_for_key(conn, subject_key)
            if subject_id is None:
                continue
            for court_id in review_court_ids:
                if ("ruled" in text_fold or "vacated" in text_fold or "unconstitutional" in text_fold) and ("court" in text_fold or "circuit" in text_fold):
                    _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="forum", entity_id=court_id, note="ruled_by_v1")
                    receipts = [("subject", subject_key), ("verb", "ruled_by"), ("object_actor", str(court_id))]
                    _insert_relation_candidate(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        subject_entity_id=subject_id,
                        predicate_id=predicate_ids["ruled_by"],
                        object_entity_id=court_id,
                        confidence_tier=_predicate_confidence(conn, "ruled_by", receipts),
                        receipts=receipts,
                    )
                if ("challeng" in text_fold or "lawsuit" in text_fold or "sued" in text_fold) and ("court" in text_fold or "circuit" in text_fold):
                    _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="forum", entity_id=court_id, note="challenged_in_v1")
                    receipts = [("subject", subject_key), ("verb", "challenged_in"), ("object_actor", str(court_id))]
                    _insert_relation_candidate(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        subject_entity_id=subject_id,
                        predicate_id=predicate_ids["challenged_in"],
                        object_entity_id=court_id,
                        confidence_tier=_predicate_confidence(conn, "challenged_in", receipts),
                        receipts=receipts,
                    )
                if ("review" in text_fold or "reaching" in text_fold or "reached" in text_fold or "considered" in text_fold) and (
                    "court" in text_fold or "circuit" in text_fold
                ):
                    _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind="forum", entity_id=court_id, note="subject_of_review_by_v1")
                    receipts = [("subject", subject_key), ("verb", "subject_of_review_by"), ("object_actor", str(court_id))]
                    _insert_relation_candidate(
                        conn,
                        run_id=run_id,
                        event_id=event_id,
                        subject_entity_id=subject_id,
                        predicate_id=predicate_ids["subject_of_review_by"],
                        object_entity_id=court_id,
                        confidence_tier=_predicate_confidence(conn, "subject_of_review_by", receipts),
                        receipts=receipts,
                    )

    _insert_broader_source_seed_backfill_candidates(
        conn,
        run_id=run_id,
        event_id=event_id,
        event=event,
        mention_clusters=mention_clusters,
        entity_ids=entity_ids,
        predicate_ids=predicate_ids,
    )


def run_gwb_semantic_pipeline(
    conn: sqlite3.Connection,
    *,
    timeline_suffix: str = "wiki_timeline_gwb.json",
    run_id: str | None = None,
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    active_run_id = run_id or _pick_best_run_for_timeline_suffix(conn, timeline_suffix)
    if not active_run_id:
        raise ValueError(f"no wiki timeline run found for suffix {timeline_suffix}")
    run_gwb_us_law_linkage(conn, timeline_suffix=timeline_suffix, run_id=active_run_id)
    payload = load_run_payload_from_normalized(conn, active_run_id)
    if not payload:
        raise ValueError(f"unable to load normalized payload for run_id={active_run_id}")
    _delete_run_rows(conn, active_run_id)
    entity_ids = _seed_entities(conn)
    predicate_ids = _ensure_predicates(conn)
    event_map = _event_map(payload)
    for event_id, event in event_map.items():
        mention_clusters = _detect_mentions_for_event(
            conn,
            run_id=active_run_id,
            event_id=event_id,
            event=event,
            entity_ids=entity_ids,
        )
        # Refresh legal refs that may have been created on this event.
        for key in list(mention_clusters):
            if key.startswith("legal_ref:"):
                entity_id = _entity_for_key(conn, key)
                if entity_id is not None:
                    entity_ids[key] = entity_id
        _extract_event_relations(
            conn,
            run_id=active_run_id,
            event_id=event_id,
            event=event,
            mention_clusters=mention_clusters,
            entity_ids=entity_ids,
            predicate_ids=predicate_ids,
        )
    entity_count = int(conn.execute("SELECT COUNT(*) FROM semantic_entities").fetchone()[0])
    candidate_count = int(conn.execute("SELECT COUNT(*) FROM semantic_relation_candidates WHERE run_id = ?", (active_run_id,)).fetchone()[0])
    promoted_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_relations
            WHERE candidate_id IN (SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?)
            """,
            (active_run_id,),
        ).fetchone()[0]
    )
    abstained_resolutions = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_mention_resolutions
            WHERE cluster_id IN (SELECT cluster_id FROM semantic_mention_clusters WHERE run_id = ?)
              AND resolution_status = 'abstained'
            """,
            (active_run_id,),
        ).fetchone()[0]
    )
    return {
        "run_id": active_run_id,
        "entity_count": entity_count,
        "relation_candidate_count": candidate_count,
        "promoted_relation_count": promoted_count,
        "abstained_resolution_count": abstained_resolutions,
    }


_TEXT_DEBUG_RECEIPT_PRIORITY: tuple[str, ...] = (
    "cue_surface",
    "verb",
    "role_marker",
    "authority_title",
    "provenance_cue",
)


def _source_document_title(source_document_id: str) -> str:
    raw = str(source_document_id or "").strip()
    if not raw:
        return "Source document"
    candidate = Path(raw)
    if candidate.name:
        return candidate.name
    return raw


def _build_timeline_source_documents(
    payload: Mapping[str, Any],
    *,
    fallback_source_document_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    documents_by_id: dict[str, dict[str, Any]] = {}
    event_spans: dict[str, dict[str, Any]] = {}
    source_timeline = payload.get("source_timeline") if isinstance(payload.get("source_timeline"), Mapping) else {}
    default_source_document_id = str(source_timeline.get("path") or fallback_source_document_id).strip() or fallback_source_document_id
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("event_id") or "").strip()
        text = str(event.get("text") or "").strip()
        if not event_id or not text:
            continue
        source_document_id = str(event.get("source_id") or default_source_document_id).strip() or default_source_document_id
        source_type = str(event.get("source_type") or "timeline_payload")
        document = documents_by_id.setdefault(
            source_document_id,
            {
                "sourceDocumentId": source_document_id,
                "sourceType": source_type,
                "title": _source_document_title(source_document_id),
                "text_parts": [],
                "eventCount": 0,
                "eventIds": [],
            },
        )
        cursor = sum(len(part) for part in document["text_parts"])
        if document["text_parts"]:
            separator = "\n\n"
            document["text_parts"].append(separator)
            cursor += len(separator)
        start = cursor
        document["text_parts"].append(text)
        end = start + len(text)
        document["eventCount"] += 1
        document["eventIds"].append(event_id)
        event_spans[event_id] = {
            "source_document_id": source_document_id,
            "source_char_start": start,
            "source_char_end": end,
        }
    documents: list[dict[str, Any]] = []
    for row in documents_by_id.values():
        documents.append(
            {
                "sourceDocumentId": row["sourceDocumentId"],
                "sourceType": row["sourceType"],
                "title": row["title"],
                "text": "".join(row["text_parts"]),
                "eventCount": row["eventCount"],
                "eventIds": row["eventIds"],
            }
        )
    documents.sort(key=lambda row: (str(row["sourceType"]), str(row["title"]), str(row["sourceDocumentId"])))
    return documents, event_spans


def _text_debug_relation_family(predicate_key: str) -> tuple[str, str]:
    if predicate_key in {"ruled_by", "challenged_in", "subject_of_review_by", "appealed", "challenged", "heard_by", "decided_by"}:
        return ("review", "#2563eb")
    if predicate_key in {"applied", "followed", "distinguished", "held_that"}:
        return ("authority", "#059669")
    if predicate_key in {"signed", "vetoed", "nominated", "confirmed_by", "authorized", "funded_by", "sanctioned"}:
        return ("governance", "#d97706")
    if predicate_key in {"replied_to"}:
        return ("conversation", "#e11d48")
    if predicate_key in {"felt_state"}:
        return ("state", "#7c3aed")
    if predicate_key in {"sibling_of", "parent_of", "child_of", "spouse_of", "friend_of", "guardian_of", "caregiver_of"}:
        return ("social", "#0f766e")
    return ("semantic", "#475569")


def _text_debug_confidence_opacity(confidence_tier: str, promotion_status: str) -> float:
    base = 0.0
    if confidence_tier == "high":
        base = 0.92
    elif confidence_tier == "medium":
        base = 0.7
    elif confidence_tier == "low":
        base = 0.42
    if promotion_status == "promoted":
        return base
    return max(0.18, round(base * 0.82, 3))


def _text_debug_tokenize(text: str) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "text": str(match.group(0)),
            "start": int(match.start()),
            "end": int(match.end()),
        }
        for index, match in enumerate(re.finditer(r"[A-Za-z0-9][A-Za-z0-9.'’:/-]*", text))
    ]


def _normalize_surface(text: str) -> str:
    return " ".join(text.strip().split())


def _text_debug_find_surface_range(text: str, surface: str) -> tuple[int, int] | None:
    trimmed = _normalize_surface(surface)
    if not trimmed:
        return None
    match = re.search(re.escape(trimmed), text, flags=re.IGNORECASE)
    if match is None:
        return None
    return (int(match.start()), int(match.end()))


def _text_debug_char_range_to_token_range(tokens: list[dict[str, Any]], start: int, end: int) -> tuple[int, int] | None:
    overlapping = [token for token in tokens if int(token["end"]) > start and int(token["start"]) < end]
    if not overlapping:
        return None
    return (int(overlapping[0]["index"]), int(overlapping[-1]["index"]))


def _text_debug_entity_anchor(
    *,
    text: str,
    tokens: list[dict[str, Any]],
    mentions: list[dict[str, Any]],
    entity: dict[str, Any],
    fallback_label: str,
) -> tuple[int, int, int, int, str, str] | None:
    for mention in mentions:
        resolved = mention.get("resolved_entity")
        if (
            mention.get("resolution_status") == "resolved"
            and isinstance(resolved, dict)
            and str(resolved.get("canonical_key", "")) == str(entity.get("canonical_key", ""))
        ):
            char_range = _text_debug_find_surface_range(text, str(mention.get("surface_text", "")))
            token_range = _text_debug_char_range_to_token_range(tokens, *char_range) if char_range else None
            if token_range:
                return (
                    token_range[0],
                    token_range[1],
                    int(char_range[0]),
                    int(char_range[1]),
                    "mention",
                    f"mention_cluster:{mention.get('cluster_id', 'unknown')}",
                )
    for surface in (
        fallback_label,
        str(entity.get("canonical_key", "")).split(":")[-1].replace("_", " "),
    ):
        char_range = _text_debug_find_surface_range(text, surface)
        token_range = _text_debug_char_range_to_token_range(tokens, *char_range) if char_range else None
        if token_range:
            return (
                token_range[0],
                token_range[1],
                int(char_range[0]),
                int(char_range[1]),
                "label_fallback",
                f"label_fallback:{entity.get('canonical_key', 'unknown')}",
            )
    return None


def _text_debug_predicate_anchor(
    *,
    text: str,
    tokens: list[dict[str, Any]],
    relation: dict[str, Any],
) -> tuple[int, int, int, int, str, str] | None:
    receipts = relation.get("receipts", [])
    if isinstance(receipts, list):
        for kind in _TEXT_DEBUG_RECEIPT_PRIORITY:
            receipt = next(
                (
                    row for row in receipts
                    if isinstance(row, dict)
                    and str(row.get("kind", "")) == kind
                    and str(row.get("value", "")).strip()
                ),
                None,
            )
            if receipt is None:
                continue
            for surface in (str(receipt.get("value", "")), str(receipt.get("value", "")).replace("_", " ")):
                char_range = _text_debug_find_surface_range(text, surface)
                token_range = _text_debug_char_range_to_token_range(tokens, *char_range) if char_range else None
                if token_range:
                    return (
                        token_range[0],
                        token_range[1],
                        int(char_range[0]),
                        int(char_range[1]),
                        "receipt",
                        f"candidate_receipt:{relation.get('candidate_id', 'unknown')}:{kind}",
                    )
    fallback_label = str(relation.get("display_label") or relation.get("predicate_key") or "").replace("_", " ")
    char_range = _text_debug_find_surface_range(text, fallback_label)
    token_range = _text_debug_char_range_to_token_range(tokens, *char_range) if char_range else None
    if token_range:
        return (
            token_range[0],
            token_range[1],
            int(char_range[0]),
            int(char_range[1]),
            "label_fallback",
            f"label_fallback:{relation.get('candidate_id', 'unknown')}:predicate",
        )
    return None


def build_semantic_text_debug_payload(per_event: list[dict[str, Any]]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for event in per_event:
        text = str(event.get("text") or "").strip()
        if not text:
            continue
        tokens = _text_debug_tokenize(text)
        if not tokens:
            continue
        mentions = list(event.get("mentions", [])) if isinstance(event.get("mentions"), list) else []
        rows = []
        for key in ("promoted_relations", "candidate_only_relations"):
            value = event.get(key)
            if isinstance(value, list):
                rows.extend(value)
        relations: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            subject = row.get("subject")
            object_ = row.get("object")
            if not isinstance(subject, dict) or not isinstance(object_, dict):
                continue
            subject_range = _text_debug_entity_anchor(
                text=text,
                tokens=tokens,
                mentions=mentions,
                entity=subject,
                fallback_label=str(subject.get("canonical_label") or ""),
            )
            object_range = _text_debug_entity_anchor(
                text=text,
                tokens=tokens,
                mentions=mentions,
                entity=object_,
                fallback_label=str(object_.get("canonical_label") or ""),
            )
            predicate_range = _text_debug_predicate_anchor(text=text, tokens=tokens, relation=row)
            anchors: list[dict[str, Any]] = []
            if subject_range:
                anchors.append(
                    {
                        "key": f"{row['candidate_id']}:subject",
                        "role": "subject",
                        "label": str(subject.get("canonical_label") or subject.get("canonical_key") or "subject"),
                        "source": subject_range[4],
                        "charStart": subject_range[2],
                        "charEnd": subject_range[3],
                        "tokenStart": subject_range[0],
                        "tokenEnd": subject_range[1],
                        "sourceArtifactId": subject_range[5],
                    }
                )
            if predicate_range:
                anchors.append(
                    {
                        "key": f"{row['candidate_id']}:predicate",
                        "role": "predicate",
                        "label": str(row.get("display_label") or row.get("predicate_key") or "predicate"),
                        "source": predicate_range[4],
                        "charStart": predicate_range[2],
                        "charEnd": predicate_range[3],
                        "tokenStart": predicate_range[0],
                        "tokenEnd": predicate_range[1],
                        "sourceArtifactId": predicate_range[5],
                    }
                )
            if object_range:
                anchors.append(
                    {
                        "key": f"{row['candidate_id']}:object",
                        "role": "object",
                        "label": str(object_.get("canonical_label") or object_.get("canonical_key") or "object"),
                        "source": object_range[4],
                        "charStart": object_range[2],
                        "charEnd": object_range[3],
                        "tokenStart": object_range[0],
                        "tokenEnd": object_range[1],
                        "sourceArtifactId": object_range[5],
                    }
                )
            if len(anchors) < 2:
                continue
            family, color = _text_debug_relation_family(str(row.get("predicate_key") or ""))
            relations.append(
                {
                    "relationId": f"{event['event_id']}:{row['candidate_id']}",
                    "predicateKey": str(row.get("predicate_key") or ""),
                    "displayLabel": str(row.get("display_label") or row.get("predicate_key") or ""),
                    "promotionStatus": str(row.get("promotion_status") or "candidate"),
                    "confidenceTier": str(row.get("confidence_tier") or "low"),
                    "family": family,
                    "color": color,
                    "opacity": _text_debug_confidence_opacity(
                        str(row.get("confidence_tier") or "low"),
                        str(row.get("promotion_status") or "candidate"),
                    ),
                    "anchors": anchors,
                }
            )
        if not relations:
            continue
        events.append(
            {
                "eventId": str(event.get("event_id") or ""),
                "text": text,
                "sourceId": str(event.get("source_id") or "") or None,
                "sourceType": str(event.get("source_type") or "") or None,
                "sourceDocumentId": str(event.get("source_document_id") or "") or None,
                "sourceCharStart": int(event["source_char_start"]) if event.get("source_char_start") is not None else None,
                "sourceCharEnd": int(event["source_char_end"]) if event.get("source_char_end") is not None else None,
                "tokenCount": len(tokens),
                "relationCount": len(relations),
                "promotedCount": sum(1 for row in relations if row["promotionStatus"] == "promoted"),
                "tokens": tokens,
                "relations": relations,
            }
        )
    return {
        "events": events[:24],
        "unavailableReason": None
        if events
        else "No text-rich semantic events with defensible token anchors are available for this corpus yet.",
    }


def build_semantic_review_summary(
    report: Mapping[str, Any],
    *,
    focus_predicates: set[str] | None = None,
    focus_candidate_only_note: str | None = None,
    extra_event_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    promoted_rows = list(report.get("promoted_relations", []))
    candidate_rows = list(report.get("candidate_only_relations", []))
    abstained_rows = list(report.get("abstained_relation_candidates", []))
    all_rows = [*promoted_rows, *candidate_rows, *abstained_rows]
    promoted_counts: dict[str, int] = defaultdict(int)
    candidate_counts: dict[str, int] = defaultdict(int)
    abstained_counts: dict[str, int] = defaultdict(int)
    cue_surface_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    family_counts: dict[str, int] = defaultdict(int)
    for row in all_rows:
        predicate_key = str(row.get("predicate_key") or "")
        status = str(row.get("promotion_status") or "")
        if status == "promoted":
            promoted_counts[predicate_key] += 1
        elif status == "candidate":
            candidate_counts[predicate_key] += 1
        else:
            abstained_counts[predicate_key] += 1
        family, _ = _text_debug_relation_family(predicate_key)
        family_counts[family] += 1
        receipts = row.get("receipts", [])
        if isinstance(receipts, list):
            for receipt in receipts:
                if str(receipt.get("kind")) == "cue_surface":
                    cue_surface_counts[predicate_key][str(receipt.get("value"))] += 1
    text_debug = report.get("text_debug", {}) if isinstance(report.get("text_debug"), dict) else {}
    text_debug_events = list(text_debug.get("events", [])) if isinstance(text_debug.get("events"), list) else []
    arc_ready_relation_count = sum(
        len(event.get("relations", []))
        for event in text_debug_events
        if isinstance(event, dict) and isinstance(event.get("relations"), list)
    )
    excluded_relation_count = max(0, len(all_rows) - arc_ready_relation_count)
    summary = {
        "predicate_counts": {
            "promoted": dict(sorted(promoted_counts.items())),
            "candidate_only": dict(sorted(candidate_counts.items())),
            "abstained": dict(sorted(abstained_counts.items())),
        },
        "top_cue_surfaces": {
            predicate: sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
            for predicate, counts in sorted(cue_surface_counts.items())
        },
        "family_counts": dict(sorted(family_counts.items())),
        "text_debug": {
            "event_count": len(text_debug_events),
            "relation_count": arc_ready_relation_count,
            "excluded_relation_count": excluded_relation_count,
            "unavailable_reason": text_debug.get("unavailableReason"),
        },
        "summary": report.get("summary", {}),
    }
    if extra_event_counts:
        summary["event_counts"] = dict(sorted((str(k), int(v)) for k, v in extra_event_counts.items()))
    if focus_predicates and focus_candidate_only_note and not any(predicate in focus_predicates for predicate in promoted_counts):
        summary["focus_candidate_only_note"] = focus_candidate_only_note
    return summary


def build_gwb_semantic_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    linkage = build_gwb_us_law_linkage_report(conn, run_id=run_id)
    payload = load_run_payload_from_normalized(conn, run_id) or {}
    source_documents, source_event_spans = _build_timeline_source_documents(
        payload,
        fallback_source_document_id=f"timeline_run:{run_id}",
    )
    entities = {
        int(row["entity_id"]): {
            "entity_id": int(row["entity_id"]),
            "entity_kind": str(row["entity_kind"]),
            "canonical_key": str(row["canonical_key"]),
            "canonical_label": str(row["canonical_label"]),
        }
        for row in conn.execute(
            "SELECT entity_id, entity_kind, canonical_key, canonical_label FROM semantic_entities ORDER BY entity_id"
        ).fetchall()
    }
    event_roles_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in conn.execute(
        """
        SELECT event_id, role_kind, entity_id, note
        FROM semantic_event_roles
        WHERE run_id = ?
        ORDER BY event_id, role_kind, role_id
        """,
        (run_id,),
    ).fetchall():
        entity = entities.get(int(row["entity_id"])) if row["entity_id"] is not None else None
        event_roles_by_event[str(row["event_id"])].append(
            {
                "role_kind": str(row["role_kind"]),
                "entity": entity,
                "note": str(row["note"] or ""),
            }
        )
    mention_rows = conn.execute(
        """
        SELECT c.cluster_id, c.event_id, c.surface_text, c.canonical_key_hint, c.source_rule,
               r.resolution_status, r.resolution_rule, r.resolved_entity_id
        FROM semantic_mention_clusters AS c
        JOIN semantic_mention_resolutions AS r ON r.cluster_id = c.cluster_id
        WHERE c.run_id = ?
        ORDER BY c.event_id, c.cluster_id
        """,
        (run_id,),
    ).fetchall()
    unresolved_mentions: list[dict[str, Any]] = []
    per_event_mentions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mention_rows:
        resolved = entities.get(int(row["resolved_entity_id"])) if row["resolved_entity_id"] is not None else None
        entry = {
            "cluster_id": int(row["cluster_id"]),
            "surface_text": str(row["surface_text"]),
            "canonical_key_hint": str(row["canonical_key_hint"] or ""),
            "source_rule": str(row["source_rule"]),
            "resolution_status": str(row["resolution_status"]),
            "resolution_rule": str(row["resolution_rule"]),
            "resolved_entity": resolved,
        }
        per_event_mentions[str(row["event_id"])].append(entry)
        if str(row["resolution_status"]) != "resolved":
            unresolved_mentions.append({"event_id": str(row["event_id"]), **entry})

    relation_rows = conn.execute(
        """
        SELECT c.candidate_id, c.event_id, c.promotion_status, c.confidence_tier,
               c.subject_entity_id, c.object_entity_id, p.predicate_key, p.display_label
        FROM semantic_relation_candidates AS c
        JOIN semantic_predicate_vocab AS p ON p.predicate_id = c.predicate_id
        WHERE c.run_id = ?
        ORDER BY c.event_id, c.candidate_id
        """,
        (run_id,),
    ).fetchall()
    promoted_relations: list[dict[str, Any]] = []
    candidate_relations: list[dict[str, Any]] = []
    candidate_only_relations: list[dict[str, Any]] = []
    abstained_relation_candidates: list[dict[str, Any]] = []
    per_entity: dict[int, dict[str, Any]] = {}
    for entity_id, entity in entities.items():
        per_entity[entity_id] = {
            "entity": entity,
            "promoted_relation_count": 0,
            "candidate_relation_count": 0,
            "events": set(),
        }
    for row in relation_rows:
        receipts = [
            {"kind": str(r["reason_kind"]), "value": str(r["reason_value"])}
            for r in conn.execute(
                """
                SELECT reason_kind, reason_value
                FROM semantic_relation_candidate_receipts
                WHERE candidate_id = ?
                ORDER BY receipt_order
                """,
                (int(row["candidate_id"]),),
            ).fetchall()
        ]
        entry = {
            "candidate_id": int(row["candidate_id"]),
            "event_id": str(row["event_id"]),
            "promotion_status": str(row["promotion_status"]),
            "confidence_tier": str(row["confidence_tier"]),
            "predicate_key": str(row["predicate_key"]),
            "display_label": str(row["display_label"]),
            "subject": entities[int(row["subject_entity_id"])],
            "object": entities[int(row["object_entity_id"])],
            "receipts": receipts,
        }
        candidate_relations.append(entry)
        for participant in (int(row["subject_entity_id"]), int(row["object_entity_id"])):
            per_entity[participant]["candidate_relation_count"] += 1
            per_entity[participant]["events"].add(str(row["event_id"]))
        if str(row["promotion_status"]) == "promoted":
            promoted_relations.append(entry)
            for participant in (int(row["subject_entity_id"]), int(row["object_entity_id"])):
                per_entity[participant]["promoted_relation_count"] += 1
        elif str(row["promotion_status"]) == "candidate":
            candidate_only_relations.append(entry)
        else:
            abstained_relation_candidates.append(entry)

    per_event = []
    for event in linkage["per_event"]:
        event_id = str(event["event_id"])
        source_span = source_event_spans.get(event_id, {})
        per_event.append(
            {
                **event,
                "source_id": source_span.get("source_document_id"),
                "source_type": "timeline_payload" if source_span else None,
                "source_document_id": source_span.get("source_document_id"),
                "source_char_start": source_span.get("source_char_start"),
                "source_char_end": source_span.get("source_char_end"),
                "mentions": per_event_mentions.get(event_id, []),
                "event_roles": event_roles_by_event.get(event_id, []),
                "relation_candidates": [row for row in candidate_relations if row["event_id"] == event_id],
                "candidate_only_relations": [row for row in candidate_only_relations if row["event_id"] == event_id],
                "abstained_relation_candidates": [row for row in abstained_relation_candidates if row["event_id"] == event_id],
                "promoted_relations": [row for row in promoted_relations if row["event_id"] == event_id],
            }
        )

    per_entity_rows = []
    for entity_id in sorted(per_entity):
        row = per_entity[entity_id]
        row["event_count"] = len(row["events"])
        row["events"] = sorted(row["events"])
        per_entity_rows.append(row)

    report = {
        "run_id": run_id,
        "summary": {
            "entity_count": len(entities),
            "relation_candidate_count": len(candidate_relations),
            "promoted_relation_count": len(promoted_relations),
            "candidate_only_relation_count": len(candidate_only_relations),
            "abstained_relation_candidate_count": len(abstained_relation_candidates),
            "unresolved_mention_count": len(unresolved_mentions),
        },
        "promoted_relations": promoted_relations,
        "relation_candidates": candidate_relations,
        "candidate_only_relations": candidate_only_relations,
        "abstained_relation_candidates": abstained_relation_candidates,
        "unresolved_mentions": unresolved_mentions,
        "per_entity": per_entity_rows,
        "per_event": per_event,
        "source_documents": source_documents,
        "text_debug": build_semantic_text_debug_payload(per_event),
        "gwb_us_law_linkage": linkage,
    }
    report["review_summary"] = build_semantic_review_summary(report)
    return report
