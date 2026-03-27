from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable

from src.gwb_us_law.semantic import (
    EntitySeed,
    _delete_run_rows,
    _ensure_promotion_policies,
    _ensure_shared_actor,
    _insert_cluster_and_resolution,
    _insert_event_role,
    _insert_relation_candidate,
    _policy_adjusted_confidence,
    _slug,
    _upsert_actor_alias,
    _upsert_seed_entity,
    build_semantic_review_summary,
    build_semantic_text_debug_payload,
    ensure_gwb_semantic_schema,
    load_mission_observer,
    persist_mission_observer,
)
from src.policy.semantic_promotion import build_relation_candidate, promote_relation_candidate
from src.reporting.structure_report import TextUnit
from src.text.speaker_inference import SpeakerInferenceReceipt, infer_speakers


PIPELINE_VERSION = "transcript_semantic_v1"


def _derive_relation_semantic_basis(
    *,
    receipts: list[dict[str, Any]],
    subject: dict[str, Any] | None,
    object_: dict[str, Any] | None,
) -> str:
    has_participants = bool(subject) and bool(object_)
    kinds = {str(receipt.get("kind") or "").strip() for receipt in receipts if str(receipt.get("kind") or "").strip()}
    has_subject = any(kind == "subject" or kind.startswith("subject_") for kind in kinds)
    has_object = any(kind == "object" or kind.startswith("object_") for kind in kinds)
    has_predicate = "verb" in kinds or "predicate" in kinds
    if has_participants and has_subject and has_object and has_predicate:
        return "structural"
    if has_participants and (has_subject or has_object or has_predicate):
        return "mixed"
    return "heuristic"

_TRANSCRIPT_PREDICATES = (
    ("felt_state", "felt state", "affect_state"),
    ("replied_to", "replied to", "conversational_turn"),
    ("sibling_of", "sibling of", "social_relation"),
    ("parent_of", "parent of", "social_relation"),
    ("child_of", "child of", "social_relation"),
    ("spouse_of", "spouse of", "social_relation"),
    ("friend_of", "friend of", "social_relation"),
    ("guardian_of", "guardian of", "social_relation"),
    ("caregiver_of", "caregiver of", "social_relation"),
)
_AFFECT_STATE_SURFACES = ("sad", "happy", "angry", "upset", "afraid", "worried")
_PERSON_CONTEXT_VERBS = {
    "met",
    "saw",
    "told",
    "asked",
    "called",
    "visited",
    "liked",
    "loved",
    "hated",
    "helped",
    "joined",
    "thanked",
    "emailed",
    "texted",
    "hugged",
    "missed",
    "followed",
}
_PLACE_CONTEXT_PREPOSITIONS = {"in", "at", "from", "to", "near", "inside", "outside"}
_LOWER_ENTITY_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "but",
    "or",
    "because",
    "that",
    "this",
    "those",
    "these",
    "he",
    "she",
    "they",
    "we",
    "i",
    "it",
    "my",
    "your",
    "his",
    "her",
    "their",
    "our",
    "was",
    "were",
    "is",
    "are",
    "in",
    "on",
    "at",
    "with",
    "for",
    "of",
    "to",
    "from",
    "user",
    "assistant",
    "system",
    "developer",
    "tool",
    "q",
    "a",
}
_TITLECASE_STOPWORDS = {
    "The",
    "A",
    "An",
    "And",
    "But",
    "Or",
    "Because",
    "That",
    "This",
    "Those",
    "These",
    "I",
    "Thanks",
    "Thank",
    "Today",
    "Yesterday",
    "Tomorrow",
    "Hello",
    "Hi",
    "Hey",
    "Yes",
    "No",
    "Okay",
    "Ok",
}

_SOCIAL_RELATION_MARKERS: dict[str, str] = {
    "sister": "sibling_of",
    "brother": "sibling_of",
    "sibling": "sibling_of",
    "mother": "parent_of",
    "father": "parent_of",
    "parent": "parent_of",
    "son": "child_of",
    "daughter": "child_of",
    "child": "child_of",
    "wife": "spouse_of",
    "husband": "spouse_of",
    "spouse": "spouse_of",
    "friend": "friend_of",
    "friends": "friend_of",
    "guardian": "guardian_of",
    "guardians": "guardian_of",
    "cared_for": "caregiver_of",
    "cares_for": "caregiver_of",
    "responsible_for": "guardian_of",
    "looks_after": "caregiver_of",
}
_MISSION_GENERIC_REFERENTS = {
    "it",
    "this",
    "that",
    "the feature",
    "new feature",
    "the new feature",
    "feature",
}
_MISSION_ACTION_PATTERNS = (
    re.compile(
        r"\b(?:implement|implemented|implementing|ship|shipped|shipping|finish|finished|finishing|complete|completed|completing|build|built|building)\s+(?:the\s+)?(?P<topic>[A-Za-z0-9][A-Za-z0-9 #/_-]{2,80}?(?:feature|integration|dashboard|viewer|contract|report|migration|issue|ticket|bug|workflow|seam|bridge|task|pr))(?=\s+(?:by|before)\b|[?.!,]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:work on|working on|follow up on|following up on)\s+(?:the\s+)?(?P<topic>[A-Za-z0-9][A-Za-z0-9 #/_-]{2,80}?(?:feature|integration|dashboard|viewer|contract|report|migration|issue|ticket|bug|workflow|seam|bridge|task|pr))(?=\s+(?:by|before)\b|[?.!,]|$)",
        re.IGNORECASE,
    ),
)
_MISSION_FOLLOWUP_PATTERNS = (
    re.compile(
        r"\b(?:have|has|did)\s+you\s+(?:implemented|implement|finished|finish|completed|complete|shipped|ship|done)\s+(?:the\s+)?(?P<topic>[A-Za-z0-9][A-Za-z0-9 #/_-]{1,80}?)\??$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfollow(?:ing)?\s+up\s+(?:on\s+)?(?P<topic>[A-Za-z0-9][A-Za-z0-9 #/_-]{1,80}?)\??$",
        re.IGNORECASE,
    ),
)
_MISSION_DEADLINE_PATTERNS = (
    re.compile(r"\b(?:deadline\s+is|due(?:\s+on)?|by|before)\s+(?P<deadline>[A-Za-z][A-Za-z0-9 ,:/-]{1,40})", re.IGNORECASE),
)
_MISSION_OWNER_PATTERNS = (
    re.compile(
        r"\b(?P<owner>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:will|should|needs\s+to|must)\s+(?:implement|ship|finish|complete|build)\s+(?:the\s+)?(?P<topic>[A-Za-z0-9][A-Za-z0-9 #/_-]{2,80}?(?:feature|integration|dashboard|viewer|contract|report|migration|issue|ticket|bug|workflow|seam|bridge|task|pr))(?=[?.!,]|$)",
        re.IGNORECASE,
    ),
)


def _source_document_title(source_id: str) -> str:
    raw = str(source_id or "").strip()
    if not raw:
        return "Source document"
    candidate = Path(raw)
    if candidate.name:
        return candidate.name
    return raw


def _build_transcript_source_documents(units: list[TextUnit]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    event_spans: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[TextUnit]] = defaultdict(list)
    for unit in units:
        by_source[unit.source_id].append(unit)
    for source_id, source_units in by_source.items():
        parts: list[str] = []
        cursor = 0
        event_ids: list[str] = []
        source_type = str(source_units[0].source_type) if source_units else ""
        for index, unit in enumerate(source_units):
            if index:
                separator = "\n\n"
                parts.append(separator)
                cursor += len(separator)
            start = cursor
            text = str(unit.text)
            parts.append(text)
            cursor += len(text)
            end = cursor
            event_ids.append(unit.unit_id)
            event_spans[unit.unit_id] = {
                "source_document_id": source_id,
                "source_char_start": start,
                "source_char_end": end,
            }
        documents.append(
            {
                "sourceDocumentId": source_id,
                "sourceType": source_type,
                "title": _source_document_title(source_id),
                "text": "".join(parts),
                "eventCount": len(source_units),
                "eventIds": event_ids,
            }
        )
    documents.sort(key=lambda row: (str(row["sourceType"]), str(row["title"]), str(row["sourceDocumentId"])))
    return documents, event_spans


def _normalize_mission_topic(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip(" \t\r\n?.!,;:"))
    text = re.sub(r"^(?:the|a|an)\s+", "", text, flags=re.IGNORECASE)
    return text.casefold()


def _mission_topic_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip(" \t\r\n?.!,;:"))
    text = re.sub(r"^(?:the|a|an)\s+", "", text, flags=re.IGNORECASE)
    return text


def _extract_deadline_phrase(text: str) -> str | None:
    for pattern in _MISSION_DEADLINE_PATTERNS:
        match = pattern.search(text)
        if match:
            deadline = re.sub(r"\s+", " ", str(match.group("deadline") or "").strip(" \t\r\n?.!,;:"))
            if deadline:
                return deadline
    return None


def _extract_topic_candidates(text: str) -> list[str]:
    out: list[str] = []
    for pattern in _MISSION_ACTION_PATTERNS:
        for match in pattern.finditer(text):
            topic = _mission_topic_label(str(match.group("topic") or ""))
            if topic and topic.casefold() not in {item.casefold() for item in out}:
                out.append(topic)
    return out


def _extract_followup_topics(text: str) -> list[str]:
    trimmed = str(text or "").strip()
    out: list[str] = []
    for pattern in _MISSION_FOLLOWUP_PATTERNS:
        match = pattern.search(trimmed)
        if not match:
            continue
        topic = _mission_topic_label(str(match.group("topic") or ""))
        if topic:
            out.append(topic)
    return out


def _build_transcript_mission_observer(
    *,
    run_id: str,
    units: list[TextUnit],
    per_event: list[dict[str, Any]],
) -> dict[str, Any]:
    event_map = {row["event_id"]: row for row in per_event}
    mission_nodes: dict[str, dict[str, Any]] = {}
    topic_mentions_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    followups: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    overlay_index = 0

    def ensure_mission(topic_label: str, event_id: str, source_id: str) -> dict[str, Any]:
        normalized = _normalize_mission_topic(topic_label)
        mission_id = f"mission:{_slug(source_id)}:{_slug(normalized)}"
        node = mission_nodes.get(mission_id)
        if node is None:
            node = {
                "missionId": mission_id,
                "nodeKind": "task",
                "topicLabel": _mission_topic_label(topic_label),
                "normalizedTopic": normalized,
                "status": "candidate",
                "confidence": "medium",
                "sourceId": source_id,
                "sourceEventIds": [],
                "deadline": None,
                "owners": [],
            }
            mission_nodes[mission_id] = node
        if event_id not in node["sourceEventIds"]:
            node["sourceEventIds"].append(event_id)
        return node

    def add_overlay(
        *,
        activity_event_id: str,
        annotation_id: str,
        mission_ref: dict[str, Any],
        evidence_refs: list[dict[str, Any]],
        status: str,
        confidence: str,
        note: str | None = None,
    ) -> None:
        overlays.append(
            {
                "activity_event_id": activity_event_id,
                "annotation_id": annotation_id,
                "sb_state_id": f"itir:mission:{run_id}",
                "provenance": {
                    "source": "SensibLaw",
                    "actor": "sensiblaw",
                    "pipeline_version": PIPELINE_VERSION,
                    "run_id": run_id,
                },
                "observer_kind": "itir_mission_graph_v1",
                "status": status,
                "confidence": confidence,
                "mission_refs": [mission_ref],
                "evidence_refs": evidence_refs,
                "note": note or "",
            }
        )

    for unit in units:
        event = event_map.get(unit.unit_id) or {}
        text = str(unit.text or "").strip()
        if not text:
            continue
        deadline = _extract_deadline_phrase(text)
        speaker_role = next((row for row in event.get("event_roles", []) if row.get("role_kind") == "speaker"), None)
        speaker_entity = speaker_role.get("entity") if isinstance(speaker_role, dict) else None
        followup_topics = _extract_followup_topics(text)

        for followup_topic in followup_topics:
            normalized = _normalize_mission_topic(followup_topic)
            candidates = topic_mentions_by_source.get(unit.source_id, [])
            resolved: dict[str, Any] | None = None
            if normalized and normalized not in _MISSION_GENERIC_REFERENTS:
                for candidate in reversed(candidates):
                    if normalized == candidate["normalizedTopic"] or normalized in candidate["normalizedTopic"]:
                        resolved = candidate
                        break
            if resolved is None and candidates:
                resolved = candidates[-1]
            overlay_status = "abstained"
            confidence = "low"
            evidence_refs = [
                {
                    "event_id": unit.unit_id,
                    "source_id": unit.source_id,
                    "source_document_id": event.get("source_document_id"),
                    "source_char_start": event.get("source_char_start"),
                    "source_char_end": event.get("source_char_end"),
                    "ref_kind": "followup_message",
                }
            ]
            mission_ref: dict[str, Any]
            if resolved is not None:
                node = mission_nodes.get(str(resolved["missionId"]))
                if node:
                    if deadline and not node.get("deadline"):
                        node["deadline"] = deadline
                    followups.append(
                        {
                            "eventId": unit.unit_id,
                            "sourceId": unit.source_id,
                            "speaker": str(speaker_entity["canonical_label"]) if isinstance(speaker_entity, dict) else None,
                            "followupTopic": _mission_topic_label(followup_topic),
                            "resolvedMissionId": node["missionId"],
                            "resolvedTopicLabel": node["topicLabel"],
                            "targetEventId": resolved["eventId"],
                            "status": "linked",
                            "confidence": "medium" if normalized in _MISSION_GENERIC_REFERENTS else "high",
                            "deadline": node.get("deadline"),
                        }
                    )
                    overlay_status = "linked"
                    confidence = "medium" if normalized in _MISSION_GENERIC_REFERENTS else "high"
                    evidence_refs.append(
                        {
                            "event_id": resolved["eventId"],
                            "source_id": unit.source_id,
                            "ref_kind": "resolved_topic",
                            "mission_id": node["missionId"],
                        }
                    )
                    mission_ref = {
                        "mission_id": node["missionId"],
                        "node_kind": node["nodeKind"],
                        "topic_label": node["topicLabel"],
                        "ref_type": "followup_resolution",
                    }
                else:
                    mission_ref = {
                        "mission_id": f"mission:unresolved:{_slug(unit.unit_id)}",
                        "node_kind": "task",
                        "topic_label": _mission_topic_label(followup_topic) or "unresolved follow-up",
                        "ref_type": "followup_unresolved",
                    }
            else:
                mission_ref = {
                    "mission_id": f"mission:unresolved:{_slug(unit.unit_id)}",
                    "node_kind": "task",
                    "topic_label": _mission_topic_label(followup_topic) or "unresolved follow-up",
                    "ref_type": "followup_unresolved",
                }
                followups.append(
                    {
                        "eventId": unit.unit_id,
                        "sourceId": unit.source_id,
                        "speaker": str(speaker_entity["canonical_label"]) if isinstance(speaker_entity, dict) else None,
                        "followupTopic": _mission_topic_label(followup_topic),
                        "resolvedMissionId": None,
                        "resolvedTopicLabel": None,
                        "targetEventId": None,
                        "status": "abstained",
                        "confidence": "low",
                        "deadline": deadline,
                    }
                )
            overlay_index += 1
            add_overlay(
                activity_event_id=unit.unit_id,
                annotation_id=f"obs:mission:{run_id}:{overlay_index}",
                mission_ref=mission_ref,
                evidence_refs=evidence_refs,
                status=overlay_status,
                confidence=confidence,
                note="Mission/follow-up observer overlay derived from transcript/freeform cues.",
            )

        for topic in _extract_topic_candidates(text):
            node = ensure_mission(topic, unit.unit_id, unit.source_id)
            if deadline and not node.get("deadline"):
                node["deadline"] = deadline
            topic_mentions_by_source[unit.source_id].append(
                {
                    "missionId": node["missionId"],
                    "topicLabel": node["topicLabel"],
                    "normalizedTopic": node["normalizedTopic"],
                    "eventId": unit.unit_id,
                }
            )
            if speaker_entity:
                owner = {
                    "entityId": int(speaker_entity["entity_id"]),
                    "label": str(speaker_entity["canonical_label"]),
                }
                if owner not in node["owners"]:
                    node["owners"].append(owner)
            overlay_index += 1
            add_overlay(
                activity_event_id=unit.unit_id,
                annotation_id=f"obs:mission:{run_id}:{overlay_index}",
                mission_ref={
                    "mission_id": node["missionId"],
                    "node_kind": node["nodeKind"],
                    "topic_label": node["topicLabel"],
                    "ref_type": "topic_mention",
                },
                evidence_refs=[
                    {
                        "event_id": unit.unit_id,
                        "source_id": unit.source_id,
                        "source_document_id": event.get("source_document_id"),
                        "source_char_start": event.get("source_char_start"),
                        "source_char_end": event.get("source_char_end"),
                        "ref_kind": "topic_mention",
                    }
                ],
                status="candidate",
                confidence=node["confidence"],
                note="Explicit mission/topic mention.",
            )

        for pattern in _MISSION_OWNER_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            topic = _mission_topic_label(str(match.group("topic") or ""))
            owner_label = _mission_topic_label(str(match.group("owner") or ""))
            if not topic or not owner_label:
                continue
            node = ensure_mission(topic, unit.unit_id, unit.source_id)
            owner = {"label": owner_label}
            if owner not in node["owners"]:
                node["owners"].append(owner)

    nodes = sorted(mission_nodes.values(), key=lambda row: (str(row["sourceId"]), str(row["topicLabel"])))
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


def _transcript_actor_key(source_id: str, speaker_label: str) -> str:
    return f"actor:transcript:{_slug(source_id)}:{_slug(speaker_label)}"


def _transcript_concept_key(source_id: str, label: str) -> str:
    return f"concept:transcript:{_slug(source_id)}:{_slug(label)}"


def _global_state_key(label: str) -> str:
    return f"concept:state:{_slug(label)}"


def _display_label(receipt: SpeakerInferenceReceipt) -> str:
    inferred = str(receipt.inferred_speaker or "")
    if inferred.startswith("speaker:"):
        return inferred.split(":", 1)[1].replace("_", " ").title()
    if receipt.observed_label:
        return receipt.observed_label.strip()
    return inferred or "Unknown speaker"


def _upsert_transcript_entity(
    conn: sqlite3.Connection,
    *,
    entity_kind: str,
    canonical_key: str,
    canonical_label: str,
    actor_kind: str | None = None,
    classification_tag: str | None = None,
) -> int:
    conn.execute(
        """
        INSERT INTO semantic_entities(entity_kind, canonical_key, canonical_label, review_status, pipeline_version)
        VALUES (?,?,?,?,?)
        ON CONFLICT(canonical_key)
        DO UPDATE SET canonical_label=excluded.canonical_label, review_status=excluded.review_status, pipeline_version=excluded.pipeline_version
        """,
        (entity_kind, canonical_key, canonical_label, "deterministic_v1", PIPELINE_VERSION),
    )
    row = conn.execute("SELECT entity_id FROM semantic_entities WHERE canonical_key = ?", (canonical_key,)).fetchone()
    assert row is not None
    entity_id = int(row["entity_id"])
    if entity_kind == "actor":
        shared_actor_id = _ensure_shared_actor(
            conn,
            canonical_key=canonical_key,
            display_name=canonical_label,
            actor_kind=actor_kind or "person_actor",
            pipeline_version=PIPELINE_VERSION,
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
            (entity_id, actor_kind or "person_actor", classification_tag),
        )
        _upsert_actor_alias(
            conn,
            actor_id=shared_actor_id,
            alias_text=canonical_label,
            source_kind="semantic_entity_label",
            source_ref=canonical_key,
            is_primary=True,
            pipeline_version=PIPELINE_VERSION,
        )
    return entity_id


def _ensure_transcript_actor(conn: sqlite3.Connection, *, source_id: str, speaker_label: str, classification_tag: str = "speaker") -> int:
    return _upsert_transcript_entity(
        conn,
        entity_kind="actor",
        canonical_key=_transcript_actor_key(source_id, speaker_label),
        canonical_label=speaker_label,
        actor_kind="person_actor",
        classification_tag=classification_tag,
    )


def _ensure_transcript_concept(conn: sqlite3.Connection, *, source_id: str, label: str) -> int:
    return _upsert_transcript_entity(
        conn,
        entity_kind="concept",
        canonical_key=_transcript_concept_key(source_id, label),
        canonical_label=label,
    )


def _ensure_state_concept(conn: sqlite3.Connection, *, label: str) -> int:
    return _upsert_transcript_entity(
        conn,
        entity_kind="concept",
        canonical_key=_global_state_key(label),
        canonical_label=label,
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
    _ensure_promotion_policies(conn)
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


def _surface_tokens(text: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in {"'", "-"}:
            current.append(ch)
            continue
        if current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def _is_titlecase_name_token(token: str) -> bool:
    if not token or token in _TITLECASE_STOPWORDS:
        return False
    letters = [ch for ch in token if ch.isalpha()]
    if not letters:
        return False
    return token[0].isupper() and any(ch.islower() for ch in letters[1:])


def _looks_like_noise_titlecase(token: str) -> bool:
    return token in _TITLECASE_STOPWORDS


def _is_likely_place_context(tokens: list[str], index: int) -> bool:
    if index <= 0:
        return False
    return tokens[index - 1].casefold() in _PLACE_CONTEXT_PREPOSITIONS


def _is_likely_person_context(tokens: list[str], index: int) -> bool:
    previous = tokens[index - 1].casefold() if index > 0 else ""
    nxt = tokens[index + 1].casefold() if index + 1 < len(tokens) else ""
    return previous in _PERSON_CONTEXT_VERBS or nxt in _PERSON_CONTEXT_VERBS


def _should_keep_single_titlecase_entity(tokens: list[str], index: int) -> bool:
    token = tokens[index]
    if _looks_like_noise_titlecase(token):
        return False
    if _is_likely_place_context(tokens, index):
        return True
    if _is_likely_person_context(tokens, index):
        return True
    return False


def _normalize_entity_surface_token(token: str) -> str:
    if token.endswith("'s") or token.endswith("’s"):
        return token[:-2]
    return token


def _extract_general_named_entities(text: str) -> list[str]:
    tokens = _surface_tokens(text)
    entities: list[str] = []
    index = 0
    while index < len(tokens):
        token = _normalize_entity_surface_token(tokens[index])
        if not _is_titlecase_name_token(token):
            index += 1
            continue
        parts = [token]
        next_token = _normalize_entity_surface_token(tokens[index + 1]) if index + 1 < len(tokens) else ""
        if next_token and _is_titlecase_name_token(next_token):
            parts.append(next_token)
            index += 1
        elif not _should_keep_single_titlecase_entity(tokens, index):
            index += 1
            continue
        label = " ".join(parts)
        if label not in entities:
            entities.append(label)
        index += 1
    return entities


def _social_relation_matches(text: str) -> list[tuple[str, str, str, str]]:
    name_pat = r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*"
    patterns = (
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+is\s+(?P<object>{name_pat})(?:'s|’s)\s+(?P<marker>sister|brother|sibling|mother|father|parent|son|daughter|child|wife|husband|spouse|friend|guardian)\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+is\s+the\s+(?P<marker>mother|father|parent|son|daughter|child|wife|husband|spouse|friend|guardian)\s+of\s+(?P<object>{name_pat})\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+and\s+(?P<object>{name_pat})\s+are\s+(?P<marker>friends|siblings|spouses)\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+is\s+(?P<marker>friends?)\s+with\s+(?P<object>{name_pat})\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+(?P<marker>cared\s+for|cares\s+for)\s+(?P<object>{name_pat})\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+is\s+responsible\s+for\s+(?P<object>{name_pat})\b"
        ),
        re.compile(
            rf"\b(?P<subject>{name_pat})\s+looks\s+after\s+(?P<object>{name_pat})\b"
        ),
    )
    matches: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            subject = str(match.group("subject")).strip()
            obj = str(match.group("object")).strip()
            marker = str(match.groupdict().get("marker") or "").strip().casefold().replace(" ", "_")
            if not marker:
                matched_text = str(match.group(0)).casefold()
                if "responsible for" in matched_text:
                    marker = "responsible_for"
                elif "looks after" in matched_text:
                    marker = "looks_after"
            if not subject or not obj or subject.casefold() == obj.casefold():
                continue
            predicate_key = _SOCIAL_RELATION_MARKERS.get(marker)
            if predicate_key is None and marker == "siblings":
                predicate_key = "sibling_of"
            if predicate_key is None and marker == "spouses":
                predicate_key = "spouse_of"
            if predicate_key is None:
                continue
            dedupe_key = (predicate_key, subject.casefold(), obj.casefold())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            matches.append((predicate_key, subject, obj, marker))
    return matches


def _extract_theme_concepts(text: str) -> list[str]:
    tokens = _surface_tokens(text)
    themes: list[str] = []
    for index in range(len(tokens) - 1):
        lowered = tokens[index].casefold()
        nxt = tokens[index + 1].casefold()
        if lowered in {"have", "having", "wanted", "wanting"} and nxt in {"my", "his", "her", "their", "our", "a", "an", "the"}:
            if index + 2 < len(tokens):
                label = tokens[index + 2].strip(".,;:!?")
                if label and label.casefold() not in _LOWER_ENTITY_STOPWORDS and label not in themes:
                    themes.append(label)
        if lowered in {"because", "without"} and index + 1 < len(tokens):
            label = tokens[index + 1].strip(".,;:!?")
            if label and label.casefold() not in _LOWER_ENTITY_STOPWORDS and label not in themes:
                themes.append(label)
    return themes


def _event_role_exists(conn: sqlite3.Connection, *, run_id: str, event_id: str, role_kind: str, entity_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM semantic_event_roles
        WHERE run_id = ? AND event_id = ? AND role_kind = ? AND entity_id = ?
        LIMIT 1
        """,
        (run_id, event_id, role_kind, entity_id),
    ).fetchone()
    return row is not None


def _insert_event_role_once(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    event_id: str,
    role_kind: str,
    entity_id: int,
    cluster_id: int | None = None,
    note: str | None = None,
) -> None:
    if _event_role_exists(conn, run_id=run_id, event_id=event_id, role_kind=role_kind, entity_id=entity_id):
        return
    _insert_event_role(conn, run_id=run_id, event_id=event_id, role_kind=role_kind, entity_id=entity_id, cluster_id=cluster_id, note=note)


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
    general_actor_by_unit: dict[str, int] = {}
    general_actor_labels_by_unit: dict[str, dict[str, int]] = {}

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
            _insert_event_role_once(
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

        if receipt.abstain_reason == "timing_only":
            continue

        named_entities = _extract_general_named_entities(unit.text)
        actor_ids_by_label: dict[str, int] = {}
        for index, label in enumerate(named_entities):
            if (
                str(receipt.inferred_speaker or "").startswith("role:")
                and receipt.observed_label
                and label.casefold() == receipt.observed_label.casefold()
            ):
                continue
            entity_id = _ensure_transcript_actor(conn, source_id=unit.source_id, speaker_label=label, classification_tag="general_actor")
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="actor",
                canonical_key_hint=_transcript_actor_key(unit.source_id, label),
                surface_text=label,
                source_rule="transcript_general_entity_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="general_named_entity_v1",
                receipts=[("surface", label), ("entity_scope", "source_local_general"), ("position", "subject" if index == 0 else "mentioned_entity")],
                pipeline_version=PIPELINE_VERSION,
            )
            actor_ids_by_label[label.casefold()] = entity_id
            if index == 0:
                general_actor_by_unit[event_id] = entity_id
                _insert_event_role_once(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    role_kind="subject",
                    entity_id=entity_id,
                    cluster_id=cluster_id,
                    note="transcript_general_entity_v1",
                )
            else:
                _insert_event_role_once(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    role_kind="mentioned_entity",
                    entity_id=entity_id,
                    cluster_id=cluster_id,
                    note="transcript_general_entity_v1",
                )
        if actor_ids_by_label:
            general_actor_labels_by_unit[event_id] = actor_ids_by_label

        theme_labels = _extract_theme_concepts(unit.text)
        theme_entity_ids: list[int] = []
        for label in theme_labels:
            entity_id = _ensure_transcript_concept(conn, source_id=unit.source_id, label=label)
            theme_entity_ids.append(entity_id)
            cluster_id, _ = _insert_cluster_and_resolution(
                conn,
                run_id=run_id,
                event_id=event_id,
                mention_kind="concept",
                canonical_key_hint=_transcript_concept_key(unit.source_id, label),
                surface_text=label,
                source_rule="transcript_theme_concept_v1",
                resolved_entity_id=entity_id,
                resolution_status="resolved",
                resolution_rule="theme_concept_v1",
                receipts=[("surface", label), ("concept_scope", "source_local_theme")],
                pipeline_version=PIPELINE_VERSION,
            )
            _insert_event_role_once(
                conn,
                run_id=run_id,
                event_id=event_id,
                role_kind="theme",
                entity_id=entity_id,
                cluster_id=cluster_id,
                note="transcript_theme_concept_v1",
            )

        subject_entity_id = actor_by_unit.get(event_id) or general_actor_by_unit.get(event_id)
        text_fold = unit.text.casefold()
        if subject_entity_id is not None:
            for state_label in _AFFECT_STATE_SURFACES:
                if state_label not in text_fold:
                    continue
                state_entity_id = _ensure_state_concept(conn, label=state_label)
                _insert_relation_candidate(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    subject_entity_id=subject_entity_id,
                    predicate_id=predicate_ids["felt_state"],
                    object_entity_id=state_entity_id,
                    confidence_tier=_policy_adjusted_confidence(
                        conn,
                        predicate_key="felt_state",
                        receipts=[
                            ("subject_actor", str(subject_entity_id)),
                            ("object_state", str(state_entity_id)),
                            ("state_surface", state_label),
                            ("predicate", "felt_state"),
                            *([("theme_concept", str(theme_entity_ids[0]))] if theme_entity_ids else []),
                        ],
                        legacy_confidence="low",
                    ),
                    receipts=[
                        ("subject_actor", str(subject_entity_id)),
                        ("object_state", str(state_entity_id)),
                        ("state_surface", state_label),
                        ("predicate", "felt_state"),
                        *([("theme_concept", str(theme_entity_ids[0]))] if theme_entity_ids else []),
                    ],
                    pipeline_version=PIPELINE_VERSION,
                )
                break

        social_actor_map = general_actor_labels_by_unit.get(event_id, {})
        for predicate_key, subject_label, object_label, marker in _social_relation_matches(unit.text):
            subject_actor_id = social_actor_map.get(subject_label.casefold())
            if subject_actor_id is None:
                subject_actor_id = _ensure_transcript_actor(
                    conn,
                    source_id=unit.source_id,
                    speaker_label=subject_label,
                    classification_tag="general_actor",
                )
                social_actor_map[subject_label.casefold()] = subject_actor_id
            object_actor_id = social_actor_map.get(object_label.casefold())
            if object_actor_id is None:
                object_actor_id = _ensure_transcript_actor(
                    conn,
                    source_id=unit.source_id,
                    speaker_label=object_label,
                    classification_tag="general_actor",
                )
                social_actor_map[object_label.casefold()] = object_actor_id
            general_actor_labels_by_unit[event_id] = social_actor_map
            if event_id not in general_actor_by_unit:
                general_actor_by_unit[event_id] = subject_actor_id
                _insert_event_role_once(
                    conn,
                    run_id=run_id,
                    event_id=event_id,
                    role_kind="subject",
                    entity_id=subject_actor_id,
                    note="transcript_social_relation_v1",
                )
            _insert_event_role_once(
                conn,
                run_id=run_id,
                event_id=event_id,
                role_kind="related_person",
                entity_id=object_actor_id,
                note="transcript_social_relation_v1",
            )
            receipts_payload = [
                ("subject_actor", str(subject_actor_id)),
                ("object_actor", str(object_actor_id)),
                ("relation_surface", marker),
                ("cue_surface", marker),
                ("predicate", predicate_key),
            ]
            _insert_relation_candidate(
                conn,
                run_id=run_id,
                event_id=event_id,
                subject_entity_id=subject_actor_id,
                predicate_id=predicate_ids[predicate_key],
                object_entity_id=object_actor_id,
                confidence_tier=_policy_adjusted_confidence(
                    conn,
                    predicate_key=predicate_key,
                    receipts=receipts_payload,
                    legacy_confidence="low",
                ),
                receipts=receipts_payload,
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
                ("predicate", "replied_to"),
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
                confidence_tier=_policy_adjusted_confidence(
                    conn,
                    predicate_key="replied_to",
                    receipts=receipts_payload,
                    legacy_confidence="low",
                ),
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
    source_documents, source_event_spans = _build_transcript_source_documents(ordered_units)
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
        subject = entities[int(row["subject_entity_id"])]
        object_ = entities[int(row["object_entity_id"])]
        semantic_basis = _derive_relation_semantic_basis(receipts=receipts, subject=subject, object_=object_)
        semantic_candidate = build_relation_candidate(
            basis=semantic_basis,
            event_id=str(row["event_id"]),
            predicate_key=str(row["predicate_key"]),
            subject=subject,
            object=object_,
            lane_promotion_status=str(row["promotion_status"]),
            confidence_tier=str(row["confidence_tier"]),
            receipts=receipts,
            rule_ids=[
                str(receipt.get("value"))
                for receipt in receipts
                if str(receipt.get("kind") or "") == "rule_type" and str(receipt.get("value") or "").strip()
            ],
        )
        promotion = promote_relation_candidate(semantic_candidate)
        candidate_rows.append(
            {
                "candidate_id": int(row["candidate_id"]),
                "event_id": str(row["event_id"]),
                "promotion_status": str(row["promotion_status"]),
                "confidence_tier": str(row["confidence_tier"]),
                "predicate_key": str(row["predicate_key"]),
                "display_label": str(row["display_label"]),
                "subject": subject,
                "object": object_,
                "receipts": receipts,
                "semantic_candidate": semantic_candidate,
                "semantic_basis": semantic_basis,
                "canonical_promotion_status": promotion["status"],
                "canonical_promotion_basis": promotion["basis"],
                "canonical_promotion_reason": promotion["reason"],
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
        source_span = source_event_spans.get(unit.unit_id, {})
        per_event.append(
            {
                "event_id": unit.unit_id,
                "source_id": unit.source_id,
                "source_type": unit.source_type,
                "source_document_id": source_span.get("source_document_id"),
                "source_char_start": source_span.get("source_char_start"),
                "source_char_end": source_span.get("source_char_end"),
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
    report = {
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
        "source_documents": source_documents,
        "text_debug": build_semantic_text_debug_payload(per_event),
    }
    mission_observer = _build_transcript_mission_observer(run_id=run_id, units=ordered_units, per_event=per_event)
    persist_mission_observer(
        conn,
        run_id=run_id,
        source="transcript",
        mission_observer=mission_observer,
        pipeline_version=PIPELINE_VERSION,
    )
    report["mission_observer"] = load_mission_observer(conn, run_id=run_id)
    social_predicates = {
        "sibling_of",
        "parent_of",
        "child_of",
        "spouse_of",
        "friend_of",
        "guardian_of",
        "caregiver_of",
    }
    social_event_counts: dict[str, int] = defaultdict(int)
    for row in candidate_only:
        predicate_key = str(row["predicate_key"])
        if predicate_key in social_predicates:
            social_event_counts[str(row["event_id"])] += 1
    report["review_summary"] = build_semantic_review_summary(
        report,
        focus_predicates=social_predicates,
        focus_candidate_only_note="All explicit social/care predicates remain candidate-only in this run.",
        extra_event_counts=social_event_counts,
    )
    return report


def build_transcript_relation_summary(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    units: Iterable[TextUnit],
) -> dict[str, Any]:
    report = build_transcript_semantic_report(conn, run_id=run_id, units=units)
    summary = dict(report.get("review_summary", {}))
    summary["run_id"] = run_id
    summary["mission_observer"] = report.get("mission_observer", {}).get("summary", {})
    if "event_counts" in summary and "social_event_counts" not in summary:
        summary["social_event_counts"] = summary["event_counts"]
    if "focus_candidate_only_note" in summary and "social_candidate_only_note" not in summary:
        summary["social_candidate_only_note"] = summary["focus_candidate_only_note"]
    return summary
