from __future__ import annotations

from collections import defaultdict
import sqlite3
from typing import Any, Iterable

from src.gwb_us_law.semantic import (
    EntitySeed,
    _delete_run_rows,
    _insert_cluster_and_resolution,
    _insert_event_role,
    _insert_relation_candidate,
    _slug,
    _upsert_seed_entity,
    ensure_gwb_semantic_schema,
)
from src.reporting.structure_report import TextUnit
from src.text.speaker_inference import SpeakerInferenceReceipt, infer_speakers


PIPELINE_VERSION = "transcript_semantic_v1"

_TRANSCRIPT_PREDICATES = (
    ("replied_to", "replied to", "conversational_turn"),
)


def _transcript_actor_key(source_id: str, speaker_label: str) -> str:
    return f"actor:transcript:{_slug(source_id)}:{_slug(speaker_label)}"


def _display_label(receipt: SpeakerInferenceReceipt) -> str:
    inferred = str(receipt.inferred_speaker or "")
    if inferred.startswith("speaker:"):
        return inferred.split(":", 1)[1].replace("_", " ").title()
    if receipt.observed_label:
        return receipt.observed_label.strip()
    return inferred or "Unknown speaker"


def _ensure_transcript_actor(conn: sqlite3.Connection, *, source_id: str, speaker_label: str) -> int:
    return _upsert_seed_entity(
        conn,
        EntitySeed(
            entity_kind="actor",
            canonical_key=_transcript_actor_key(source_id, speaker_label),
            canonical_label=speaker_label,
            actor_kind="person_actor",
            classification_tag="speaker",
            aliases=(speaker_label,),
        ),
        pipeline_version=PIPELINE_VERSION,
    )


def _ensure_transcript_predicates(conn: sqlite3.Connection) -> dict[str, int]:
    for predicate_key, display_label, family in _TRANSCRIPT_PREDICATES:
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
            (predicate_key, display_label, family, 1, None, f"transcript_{predicate_key}_v1"),
        )
    rows = conn.execute("SELECT predicate_id, predicate_key FROM semantic_predicate_vocab").fetchall()
    return {str(row["predicate_key"]): int(row["predicate_id"]) for row in rows}


def _speaker_receipts(receipt: SpeakerInferenceReceipt) -> list[tuple[str, str]]:
    out = [("confidence", receipt.confidence)]
    if receipt.observed_label:
        out.append(("observed_label", receipt.observed_label))
    if receipt.inferred_speaker:
        out.append(("inferred_speaker", receipt.inferred_speaker))
    for reason in receipt.reasons:
        out.append(("speaker_reason", reason))
    return out


def run_transcript_semantic_pipeline(
    conn: sqlite3.Connection,
    units: Iterable[TextUnit],
    *,
    known_participants_by_source: dict[str, list[str]] | None = None,
    run_id: str = "transcript-semantic-v1",
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    _delete_run_rows(conn, run_id)
    predicate_ids = _ensure_transcript_predicates(conn)
    ordered_units = list(units)
    receipts = infer_speakers(ordered_units, known_participants_by_source=known_participants_by_source)
    actor_by_unit: dict[str, int] = {}

    for unit, receipt in zip(ordered_units, receipts):
        event_id = unit.unit_id
        if not receipt.abstained and str(receipt.inferred_speaker or "").startswith("speaker:"):
            label = _display_label(receipt)
            entity_id = _ensure_transcript_actor(conn, source_id=unit.source_id, speaker_label=label)
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_transcript_actor_key(unit.source_id, label),
                surface_text=label,
                source_rule="transcript_speaker_inference_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="speaker_inference_resolved_v1",
                receipts=_speaker_receipts(receipt),
                pipeline_version=PIPELINE_VERSION,
            )
            actor_by_unit[event_id] = entity_id
            _insert_event_role(
                conn,
                run_id=run_id,
                event_id=event_id,
                role_kind="speaker",
                entity_id=entity_id,
                cluster_id=cluster_id,
                note="transcript_speaker_inference_v1",
            )
            continue
        resolution_rule = "speaker_inference_abstained_v1"
        if receipt.abstain_reason == "timing_only":
            resolution_rule = "transcript_timing_only_v1"
        elif str(receipt.inferred_speaker or "").startswith("role:"):
            resolution_rule = "role_label_not_person_actor_v1"
        _insert_cluster_and_resolution(
            conn,
            run_id=run_id,
            event_id=event_id,
            mention_kind="actor",
            canonical_key_hint=None,
            surface_text=receipt.observed_label or unit.text[:80],
            source_rule="transcript_speaker_inference_v1",
            resolved_entity_id=None,
            resolution_status="abstained",
            resolution_rule=resolution_rule,
            receipts=_speaker_receipts(receipt) + [("abstain_reason", receipt.abstain_reason or "unknown")],
            pipeline_version=PIPELINE_VERSION,
        )

    by_source: dict[str, list[tuple[TextUnit, SpeakerInferenceReceipt]]] = defaultdict(list)
    for unit, receipt in zip(ordered_units, receipts):
        by_source[unit.source_id].append((unit, receipt))

    for pairs in by_source.values():
        for index in range(1, len(pairs)):
            previous_unit, previous_receipt = pairs[index - 1]
            current_unit, current_receipt = pairs[index]
            previous_actor = actor_by_unit.get(previous_unit.unit_id)
            current_actor = actor_by_unit.get(current_unit.unit_id)
            if previous_actor is None or current_actor is None or previous_actor == current_actor:
                continue
            prev_text = previous_unit.text.strip()
            q_to_a = (previous_receipt.observed_label or "").casefold() == "q" and (current_receipt.observed_label or "").casefold() == "a"
            if not q_to_a and not prev_text.endswith("?"):
                continue
            receipts_payload = [
                ("subject_actor", str(current_actor)),
                ("object_actor", str(previous_actor)),
                ("turn_signal", "qa_marker" if q_to_a else "question_turn"),
                ("source_type", current_unit.source_type),
            ]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=current_unit.unit_id,
                subject_entity_id=current_actor,
                predicate_id=predicate_ids["replied_to"],
                object_entity_id=previous_actor,
                confidence_tier="low",
                receipts=receipts_payload,
                pipeline_version=PIPELINE_VERSION,
            )

    candidate_count = int(conn.execute("SELECT COUNT(*) FROM semantic_relation_candidates WHERE run_id = ?", (run_id,)).fetchone()[0])
    promoted_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_relations
            WHERE candidate_id IN (SELECT candidate_id FROM semantic_relation_candidates WHERE run_id = ?)
            """,
            (run_id,),
        ).fetchone()[0]
    )
    abstained_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM semantic_mention_resolutions
            WHERE cluster_id IN (SELECT cluster_id FROM semantic_mention_clusters WHERE run_id = ?)
              AND resolution_status = 'abstained'
            """,
            (run_id,),
        ).fetchone()[0]
    )
    return {
        "run_id": run_id,
        "unit_count": len(ordered_units),
        "relation_candidate_count": candidate_count,
        "promoted_relation_count": promoted_count,
        "abstained_resolution_count": abstained_count,
    }


def build_transcript_semantic_report(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    units: Iterable[TextUnit],
) -> dict[str, Any]:
    ensure_gwb_semantic_schema(conn)
    ordered_units = list(units)
    event_map = {unit.unit_id: unit for unit in ordered_units}
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
        ORDER BY event_id, role_id
        """,
        (run_id,),
    ).fetchall():
        event_roles_by_event[str(row["event_id"])].append(
            {
                "role_kind": str(row["role_kind"]),
                "entity": entities.get(int(row["entity_id"])) if row["entity_id"] is not None else None,
                "note": str(row["note"] or ""),
            }
        )
    unresolved_mentions: list[dict[str, Any]] = []
    per_event_mentions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in conn.execute(
        """
        SELECT c.cluster_id, c.event_id, c.surface_text, c.canonical_key_hint, c.source_rule,
               r.resolution_status, r.resolution_rule, r.resolved_entity_id
        FROM semantic_mention_clusters AS c
        JOIN semantic_mention_resolutions AS r ON r.cluster_id = c.cluster_id
        WHERE c.run_id = ?
        ORDER BY c.event_id, c.cluster_id
        """,
        (run_id,),
    ).fetchall():
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
    candidate_rows = []
    for row in conn.execute(
        """
        SELECT c.candidate_id, c.event_id, c.promotion_status, c.confidence_tier,
               c.subject_entity_id, c.object_entity_id, p.predicate_key, p.display_label
        FROM semantic_relation_candidates AS c
        JOIN semantic_predicate_vocab AS p ON p.predicate_id = c.predicate_id
        WHERE c.run_id = ?
        ORDER BY c.event_id, c.candidate_id
        """,
        (run_id,),
    ).fetchall():
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
        candidate_rows.append(
            {
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
        )
    promoted = [row for row in candidate_rows if row["promotion_status"] == "promoted"]
    candidate_only = [row for row in candidate_rows if row["promotion_status"] == "candidate"]
    abstained = [row for row in candidate_rows if row["promotion_status"] == "abstained"]
    per_entity: dict[int, dict[str, Any]] = {}
    for entity_id, entity in entities.items():
        per_entity[entity_id] = {"entity": entity, "events": set(), "candidate_relation_count": 0, "promoted_relation_count": 0}
    for row in candidate_rows:
        for participant in (int(row["subject"]["entity_id"]), int(row["object"]["entity_id"])):
            per_entity[participant]["events"].add(row["event_id"])
            per_entity[participant]["candidate_relation_count"] += 1
            if row["promotion_status"] == "promoted":
                per_entity[participant]["promoted_relation_count"] += 1
    per_event = []
    for unit in ordered_units:
        per_event.append(
            {
                "event_id": unit.unit_id,
                "source_id": unit.source_id,
                "source_type": unit.source_type,
                "text": unit.text,
                "mentions": per_event_mentions.get(unit.unit_id, []),
                "event_roles": event_roles_by_event.get(unit.unit_id, []),
                "relation_candidates": [row for row in candidate_rows if row["event_id"] == unit.unit_id],
                "candidate_only_relations": [row for row in candidate_only if row["event_id"] == unit.unit_id],
                "abstained_relation_candidates": [row for row in abstained if row["event_id"] == unit.unit_id],
                "promoted_relations": [row for row in promoted if row["event_id"] == unit.unit_id],
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
            "unit_count": len(ordered_units),
            "relation_candidate_count": len(candidate_rows),
            "promoted_relation_count": len(promoted),
            "candidate_only_relation_count": len(candidate_only),
            "abstained_relation_candidate_count": len(abstained),
            "unresolved_mention_count": len(unresolved_mentions),
        },
        "promoted_relations": promoted,
        "relation_candidates": candidate_rows,
        "candidate_only_relations": candidate_only,
        "abstained_relation_candidates": abstained,
        "unresolved_mentions": unresolved_mentions,
        "per_entity": per_entity_rows,
        "per_event": per_event,
    }
