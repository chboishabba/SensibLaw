from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping

from src.gwb_us_law.linkage import (
    _pick_best_run_for_timeline_suffix,
    build_gwb_us_law_linkage_report,
    run_gwb_us_law_linkage,
)
from src.wiki_timeline.sqlite_store import load_run_payload_from_normalized


PIPELINE_VERSION = "gwb_semantic_v1"


def ensure_gwb_semantic_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS semantic_entities (
          entity_id INTEGER PRIMARY KEY,
          entity_kind TEXT NOT NULL,
          canonical_key TEXT NOT NULL UNIQUE,
          canonical_label TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'deterministic_v1',
          pipeline_version TEXT NOT NULL
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


def _upsert_seed_entity(conn: sqlite3.Connection, seed: EntitySeed) -> int:
    conn.execute(
        """
        INSERT INTO semantic_entities(entity_kind, canonical_key, canonical_label, review_status, pipeline_version)
        VALUES (?,?,?,?,?)
        ON CONFLICT(canonical_key)
        DO UPDATE SET canonical_label=excluded.canonical_label, review_status=excluded.review_status, pipeline_version=excluded.pipeline_version
        """,
        (seed.entity_kind, seed.canonical_key, seed.canonical_label, "deterministic_v1", PIPELINE_VERSION),
    )
    row = conn.execute("SELECT entity_id FROM semantic_entities WHERE canonical_key = ?", (seed.canonical_key,)).fetchone()
    assert row is not None
    entity_id = int(row["entity_id"])
    if seed.entity_kind == "actor":
        conn.execute(
            """
            INSERT INTO semantic_entity_actors(entity_id, actor_kind, classification_tag)
            VALUES (?,?,?)
            ON CONFLICT(entity_id) DO UPDATE SET actor_kind=excluded.actor_kind, classification_tag=excluded.classification_tag
            """,
            (entity_id, seed.actor_kind, seed.classification_tag),
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
        (cluster_id, resolved_entity_id, resolution_status, resolution_rule, PIPELINE_VERSION),
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
        for alias in seed.aliases:
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


def _predicate_confidence(predicate_key: str, receipts: list[tuple[str, str]]) -> str:
    kinds = {kind for kind, _ in receipts}
    if predicate_key in {"signed", "vetoed"} and {"subject", "object_legal_ref", "verb"} <= kinds:
        return "high"
    if predicate_key in {"nominated", "confirmed_by"} and {"subject", "object_actor", "verb"} <= kinds:
        return "high"
    if {"subject", "verb"} <= kinds:
        return "medium"
    return "low" if {"subject", "verb"} <= kinds else "abstain"


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
) -> int:
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
            "promoted" if confidence_tier in {"high", "medium"} else ("candidate" if confidence_tier == "low" else "abstained"),
            confidence_tier,
            PIPELINE_VERSION,
        ),
    )
    candidate_id = int(cur.lastrowid)
    for idx, (kind, value) in enumerate(receipts, start=1):
        conn.execute(
            """
            INSERT INTO semantic_relation_candidate_receipts(candidate_id, receipt_order, reason_kind, reason_value)
            VALUES (?,?,?,?)
            """,
            (candidate_id, idx, kind, value),
        )
    if confidence_tier in {"high", "medium"}:
        rel_cur = conn.execute(
            """
            INSERT INTO semantic_relations(
              candidate_id, subject_entity_id, predicate_id, object_entity_id, event_id, confidence_tier, pipeline_version
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (candidate_id, subject_entity_id, predicate_id, object_entity_id, event_id, confidence_tier, PIPELINE_VERSION),
        )
        relation_id = int(rel_cur.lastrowid)
        for idx, (kind, value) in enumerate(receipts, start=1):
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
                confidence_tier=_predicate_confidence("signed", receipts),
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
                confidence_tier=_predicate_confidence("vetoed", receipts),
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
                confidence_tier=_predicate_confidence("nominated", receipts),
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
                confidence_tier=_predicate_confidence("confirmed_by", receipts),
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
                        confidence_tier=_predicate_confidence("ruled_by", receipts),
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
                        confidence_tier=_predicate_confidence("challenged_in", receipts),
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
                        confidence_tier=_predicate_confidence("subject_of_review_by", receipts),
                        receipts=receipts,
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


def build_gwb_semantic_report(conn: sqlite3.Connection, *, run_id: str) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    linkage = build_gwb_us_law_linkage_report(conn, run_id=run_id)
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
        per_event.append(
            {
                **event,
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

    return {
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
        "gwb_us_law_linkage": linkage,
    }
