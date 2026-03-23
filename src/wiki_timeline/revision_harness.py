from __future__ import annotations

import json
import re
from typing import Any, Mapping

from src.text.similarity import simhash, simhash_hamming_distance, token_jaccard_similarity
from src.wiki_timeline.article_state import coalesce_snapshot, coerce_wiki_article_state

REPORT_SCHEMA_VERSION = "wiki_revision_harness_report_v0_1"
_WS_RE = re.compile(r"\s+")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _norm_text(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def _safe_str(value: Any) -> str | None:
    text = _norm_text(value)
    return text or None


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _article_identity(
    previous_snapshot: dict[str, Any],
    current_snapshot: dict[str, Any],
    previous_payload: dict[str, Any] | None,
    current_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    prev_source = previous_payload.get("source_entity") if isinstance(previous_payload, dict) else None
    curr_source = current_payload.get("source_entity") if isinstance(current_payload, dict) else None
    wiki = _safe_str(current_snapshot.get("wiki")) or _safe_str(previous_snapshot.get("wiki"))
    title = _safe_str(current_snapshot.get("title")) or _safe_str(previous_snapshot.get("title"))
    source_url = (
        _safe_str(current_snapshot.get("source_url"))
        or _safe_str(previous_snapshot.get("source_url"))
        or (curr_source.get("url") if isinstance(curr_source, dict) else None)
        or (prev_source.get("url") if isinstance(prev_source, dict) else None)
    )
    return {
        "wiki": wiki,
        "title": title,
        "source_url": source_url,
    }


def _revision_meta(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(snapshot),
        "revid": snapshot.get("revid"),
        "rev_timestamp": _safe_str(snapshot.get("rev_timestamp")),
        "fetched_at": _safe_str(snapshot.get("fetched_at")),
    }


def _extract_source_text(snapshot: Mapping[str, Any], payload: Mapping[str, Any] | None) -> str:
    wikitext = _norm_text(snapshot.get("wikitext"))
    if wikitext:
        return wikitext
    if isinstance(payload, Mapping):
        source_text = payload.get("source_text")
        if isinstance(source_text, Mapping):
            text = _norm_text(source_text.get("wikitext"))
            if text:
                return text
        events = payload.get("event_candidates") if payload.get("schema_version") else payload.get("events")
        if isinstance(events, list):
            event_texts = [_norm_text(ev.get("text")) for ev in events if isinstance(ev, Mapping)]
            joined = "\n".join(text for text in event_texts if text)
            if joined.strip():
                return joined
    return ""


def _extract_event_text_from_state(state: Mapping[str, Any] | None) -> str:
    if not isinstance(state, Mapping):
        return ""
    events = state.get("event_candidates")
    if not isinstance(events, list):
        return ""
    texts = [_norm_text(ev.get("text")) for ev in events if isinstance(ev, Mapping)]
    return "\n".join(text for text in texts if text)


def _similarity_summary(left: str, right: str) -> dict[str, Any]:
    left_norm = _norm_text(left)
    right_norm = _norm_text(right)
    left_hash = simhash(left_norm)
    right_hash = simhash(right_norm)
    return {
        "left_length": len(left_norm),
        "right_length": len(right_norm),
        "token_jaccard": round(token_jaccard_similarity(left_norm, right_norm), 6),
        "left_simhash": left_hash,
        "right_simhash": right_hash,
        "simhash_hamming_distance": simhash_hamming_distance(left_hash, right_hash),
    }


def _sentence_unit_map(state: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(state, Mapping):
        return {}
    units = state.get("sentence_units")
    if not isinstance(units, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            continue
        unit_id = _safe_str(unit.get("unit_id")) or f"unit:{index}"
        out[unit_id] = unit
    return out


def _observation_map(state: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(state, Mapping):
        return {}
    observations = state.get("observations")
    if not isinstance(observations, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            continue
        observation_id = _safe_str(observation.get("observation_id")) or f"observation:{index}"
        out[observation_id] = observation
    return out


def _event_map(state: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(state, Mapping):
        return {}
    events = state.get("event_candidates")
    if not isinstance(events, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        event_id = _safe_str(event.get("event_id")) or f"event:{index}"
        out[event_id] = event
    return out


def _normalize_actor(actor: Any) -> str | None:
    if isinstance(actor, Mapping):
        return _safe_str(actor.get("resolved")) or _safe_str(actor.get("label")) or _safe_str(actor.get("text"))
    return _safe_str(actor)


def _normalize_object(obj: Any) -> str | None:
    if isinstance(obj, Mapping):
        return _safe_str(obj.get("title")) or _safe_str(obj.get("text")) or _safe_str(obj.get("label"))
    return _safe_str(obj)


def _normalize_step_signature(step: Any) -> dict[str, Any] | None:
    if not isinstance(step, Mapping):
        return None
    return {
        "action": _safe_str(step.get("action")),
        "subjects": _sorted_unique([_safe_str(v) or "" for v in (step.get("subjects") or []) if _safe_str(v)]),
        "objects": _sorted_unique(
            [_normalize_object(v) or "" for v in (step.get("objects") or []) if _normalize_object(v)]
        ),
        "claim_bearing": bool(step.get("claim_bearing")),
    }


def _normalize_attribution_signature(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    return {
        "attributed_actor_id": _safe_str(item.get("attributed_actor_id")),
        "attribution_type": _safe_str(item.get("attribution_type")),
        "reporting_actor_id": _safe_str(item.get("reporting_actor_id")),
        "certainty_level": _safe_str(item.get("certainty_level")),
        "extraction_method": _safe_str(item.get("extraction_method")),
        "step_index": item.get("step_index"),
    }


def _event_signature(event: Mapping[str, Any]) -> dict[str, Any]:
    steps = [_normalize_step_signature(step) for step in (event.get("steps") or [])]
    attrs = [_normalize_attribution_signature(item) for item in (event.get("attributions") or [])]
    return {
        "text": _norm_text(event.get("text")),
        "action": _safe_str(event.get("action")),
        "claim_bearing": bool(event.get("claim_bearing")),
        "claim_step_indices": sorted(int(v) for v in (event.get("claim_step_indices") or []) if isinstance(v, int)),
        "actors": _sorted_unique(
            [_normalize_actor(actor) or "" for actor in (event.get("actors") or []) if _normalize_actor(actor)]
        ),
        "objects": _sorted_unique(
            [
                _normalize_object(obj) or ""
                for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects")
                for obj in (event.get(field) or [])
                if _normalize_object(obj)
            ]
        ),
        "steps": [step for step in steps if step],
        "attributions": [attr for attr in attrs if attr],
        "anchor_status": _safe_str(event.get("anchor_status")),
        "anchor": dict(event.get("anchor")) if isinstance(event.get("anchor"), Mapping) else None,
    }


def _text_unit_signature(unit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "section": _safe_str(unit.get("section")),
        "text": _safe_str(unit.get("text")),
        "anchor_status": _safe_str(unit.get("anchor_status")),
        "anchor": dict(unit.get("anchor")) if isinstance(unit.get("anchor"), Mapping) else None,
    }


def _observation_signature(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": _safe_str(observation.get("event_id")),
        "predicate": _safe_str(observation.get("predicate")),
        "object_text": _safe_str(observation.get("object_text")),
        "anchor_status": _safe_str(observation.get("anchor_status")),
        "step_index": observation.get("step_index"),
    }


def _changed_ids_by_signature(
    previous_map: Mapping[str, Mapping[str, Any]],
    current_map: Mapping[str, Mapping[str, Any]],
    signature_fn: Any,
) -> tuple[list[str], list[str], list[str]]:
    prev_ids = set(previous_map)
    curr_ids = set(current_map)
    added = sorted(curr_ids - prev_ids)
    removed = sorted(prev_ids - curr_ids)
    changed: list[str] = []
    for item_id in sorted(prev_ids & curr_ids):
        if _stable_json(signature_fn(previous_map[item_id])) != _stable_json(signature_fn(current_map[item_id])):
            changed.append(item_id)
    return added, removed, changed


def _changed_event_ids(
    previous_events: dict[str, dict[str, Any]],
    current_events: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    return _changed_ids_by_signature(previous_events, current_events, _event_signature)


def _collect_actor_surfaces(state: Mapping[str, Any] | None) -> list[str]:
    events = _event_map(state)
    values: list[str] = []
    for event in events.values():
        for actor in (event.get("actors") or []):
            value = _normalize_actor(actor)
            if value:
                values.append(value)
        for step in (event.get("steps") or []):
            if isinstance(step, Mapping):
                for subject in (step.get("subjects") or []):
                    value = _safe_str(subject)
                    if value:
                        values.append(value)
    return _sorted_unique(values)


def _collect_action_surfaces(state: Mapping[str, Any] | None) -> list[str]:
    events = _event_map(state)
    values: list[str] = []
    for event in events.values():
        action = _safe_str(event.get("action"))
        if action:
            values.append(action)
        for step in (event.get("steps") or []):
            if isinstance(step, Mapping):
                value = _safe_str(step.get("action"))
                if value:
                    values.append(value)
    return _sorted_unique(values)


def _collect_object_surfaces(state: Mapping[str, Any] | None) -> list[str]:
    events = _event_map(state)
    values: list[str] = []
    for event in events.values():
        for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            for obj in (event.get(field) or []):
                value = _normalize_object(obj)
                if value:
                    values.append(value)
        for step in (event.get("steps") or []):
            if isinstance(step, Mapping):
                for obj in (step.get("objects") or []):
                    value = _normalize_object(obj)
                    if value:
                        values.append(value)
    return _sorted_unique(values)


def _collect_claim_bearing_event_ids(state: Mapping[str, Any] | None) -> list[str]:
    events = _event_map(state)
    out: list[str] = []
    for event_id, event in events.items():
        if bool(event.get("claim_bearing")):
            out.append(event_id)
    return sorted(out)


def _collect_attribution_event_ids(state: Mapping[str, Any] | None) -> list[str]:
    events = _event_map(state)
    out: list[str] = []
    for event_id, event in events.items():
        attrs = event.get("attributions") or []
        if isinstance(attrs, list) and attrs:
            out.append(event_id)
    return sorted(out)


def _event_related_entities(previous_event: Mapping[str, Any] | None, current_event: Mapping[str, Any] | None) -> list[str]:
    values: list[str] = []
    for event in (previous_event, current_event):
        if not isinstance(event, Mapping):
            continue
        for actor in (event.get("actors") or []):
            value = _normalize_actor(actor)
            if value:
                values.append(value)
        for field in ("objects", "entity_objects"):
            for obj in (event.get(field) or []):
                value = _normalize_object(obj)
                if value:
                    values.append(value)
        for link in (event.get("links") or []):
            value = _normalize_object(link)
            if value:
                values.append(value)
    return _sorted_unique(values)[:10]


def _event_surface_diff(previous_event: Mapping[str, Any] | None, current_event: Mapping[str, Any] | None) -> tuple[list[str], list[str]]:
    surfaces: list[str] = []
    reasons: list[str] = []
    if previous_event is None or current_event is None:
        surfaces.extend(["narrative", "semantic", "logical"])
        reasons.append("event added or removed")
        if (previous_event or current_event) and bool((previous_event or current_event).get("claim_bearing")):
            surfaces.append("epistemic")
            reasons.append("claim-bearing event added or removed")
        return _sorted_unique(surfaces), reasons

    prev_sig = _event_signature(previous_event)
    curr_sig = _event_signature(current_event)
    if prev_sig["text"] != curr_sig["text"]:
        surfaces.append("narrative")
        reasons.append("event text changed")
    if prev_sig["actors"] != curr_sig["actors"] or prev_sig["steps"] != curr_sig["steps"]:
        surfaces.append("semantic")
        reasons.append("actor/step extraction changed")
    if prev_sig["objects"] != curr_sig["objects"] or prev_sig["action"] != curr_sig["action"]:
        surfaces.append("logical")
        reasons.append("action/object graph surfaces changed")
    if (
        prev_sig["claim_bearing"] != curr_sig["claim_bearing"]
        or prev_sig["claim_step_indices"] != curr_sig["claim_step_indices"]
        or prev_sig["attributions"] != curr_sig["attributions"]
    ):
        surfaces.append("epistemic")
        reasons.append("claim-bearing or attribution state changed")
    if prev_sig["anchor_status"] != curr_sig["anchor_status"] or prev_sig["anchor"] != curr_sig["anchor"]:
        surfaces.append("logical")
        reasons.append("anchor status changed")
    return _sorted_unique(surfaces), reasons


def _severity_for_surfaces(surfaces: list[str]) -> str:
    surface_set = set(surfaces)
    if "epistemic" in surface_set:
        return "high"
    if "logical" in surface_set or "semantic" in surface_set:
        return "medium"
    return "low"


def _packet_summary(reasons: list[str]) -> str:
    if not reasons:
        return "changed revision surface"
    return "; ".join(reasons[:3])


def _event_state_change_summary(previous_event: Mapping[str, Any] | None, current_event: Mapping[str, Any] | None) -> list[str]:
    changes: list[str] = []
    prev_sig = _event_signature(previous_event or {})
    curr_sig = _event_signature(current_event or {})
    if prev_sig["actors"] != curr_sig["actors"]:
        changes.append("actors")
    if prev_sig["action"] != curr_sig["action"]:
        changes.append("action")
    if prev_sig["objects"] != curr_sig["objects"]:
        changes.append("objects")
    if prev_sig["claim_bearing"] != curr_sig["claim_bearing"] or prev_sig["claim_step_indices"] != curr_sig["claim_step_indices"]:
        changes.append("claims")
    if prev_sig["attributions"] != curr_sig["attributions"]:
        changes.append("attributions")
    if prev_sig["anchor_status"] != curr_sig["anchor_status"] or prev_sig["anchor"] != curr_sig["anchor"]:
        changes.append("anchors")
    return changes


def _changed_observation_ids_for_event(
    event_id: str,
    previous_observations: Mapping[str, Mapping[str, Any]],
    current_observations: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    changed: list[str] = []
    for observation_id, observation in previous_observations.items():
        if _safe_str(observation.get("event_id")) == event_id:
            changed.append(observation_id)
    for observation_id, observation in current_observations.items():
        if _safe_str(observation.get("event_id")) == event_id:
            changed.append(observation_id)
    return _sorted_unique(changed)


def build_revision_comparison_report(
    *,
    previous_snapshot: dict[str, Any] | None = None,
    current_snapshot: dict[str, Any] | None = None,
    previous_payload: dict[str, Any] | None = None,
    current_payload: dict[str, Any] | None = None,
    review_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_snapshot_obj = coalesce_snapshot(previous_snapshot, previous_payload)
    current_snapshot_obj = coalesce_snapshot(current_snapshot, current_payload)
    article = _article_identity(previous_snapshot_obj, current_snapshot_obj, previous_payload, current_payload)

    previous_state = coerce_wiki_article_state(snapshot=previous_snapshot_obj, payload=previous_payload)
    current_state = coerce_wiki_article_state(snapshot=current_snapshot_obj, payload=current_payload)

    previous_units = _sentence_unit_map(previous_state)
    current_units = _sentence_unit_map(current_state)
    previous_observations = _observation_map(previous_state)
    current_observations = _observation_map(current_state)
    previous_events = _event_map(previous_state)
    current_events = _event_map(current_state)

    added_unit_ids, removed_unit_ids, changed_unit_ids = _changed_ids_by_signature(
        previous_units,
        current_units,
        _text_unit_signature,
    )
    added_observation_ids, removed_observation_ids, changed_observation_ids = _changed_ids_by_signature(
        previous_observations,
        current_observations,
        _observation_signature,
    )
    added_event_ids, removed_event_ids, changed_event_ids = _changed_event_ids(previous_events, current_events)

    source_text_previous = _extract_source_text(previous_snapshot_obj, previous_state)
    source_text_current = _extract_source_text(current_snapshot_obj, current_state)
    extraction_text_previous = _extract_event_text_from_state(previous_state)
    extraction_text_current = _extract_event_text_from_state(current_state)

    prev_actors = _collect_actor_surfaces(previous_state)
    curr_actors = _collect_actor_surfaces(current_state)
    prev_actions = _collect_action_surfaces(previous_state)
    curr_actions = _collect_action_surfaces(current_state)
    prev_objects = _collect_object_surfaces(previous_state)
    curr_objects = _collect_object_surfaces(current_state)
    prev_claim_ids = _collect_claim_bearing_event_ids(previous_state)
    curr_claim_ids = _collect_claim_bearing_event_ids(current_state)
    prev_attr_ids = _collect_attribution_event_ids(previous_state)
    curr_attr_ids = _collect_attribution_event_ids(current_state)
    prev_timeline_rows = [
        row for row in previous_state.get("timeline_projection") or [] if isinstance(row, Mapping)
    ] if isinstance(previous_state, Mapping) else []
    curr_timeline_rows = [
        row for row in current_state.get("timeline_projection") or [] if isinstance(row, Mapping)
    ] if isinstance(current_state, Mapping) else []
    prev_anchor_status = {str(row.get("event_id") or ""): str(row.get("anchor_status") or "none") for row in prev_timeline_rows}
    curr_anchor_status = {str(row.get("event_id") or ""): str(row.get("anchor_status") or "none") for row in curr_timeline_rows}
    changed_anchor_event_ids = sorted(
        event_id
        for event_id in set(prev_anchor_status) | set(curr_anchor_status)
        if prev_anchor_status.get(event_id) != curr_anchor_status.get(event_id)
    )

    packet_ids = sorted(set(added_event_ids + removed_event_ids + changed_event_ids))
    issue_packets: list[dict[str, Any]] = []
    for event_id in packet_ids:
        prev_event = previous_events.get(event_id)
        curr_event = current_events.get(event_id)
        surfaces, reasons = _event_surface_diff(prev_event, curr_event)
        prev_sig = _event_signature(prev_event or {})
        curr_sig = _event_signature(curr_event or {})
        packet = {
            "packet_id": f"packet:{article.get('title') or 'article'}:{event_id}",
            "event_id": event_id,
            "severity": _severity_for_surfaces(surfaces),
            "surfaces": surfaces,
            "summary": _packet_summary(reasons),
            "previous_event_present": prev_event is not None,
            "current_event_present": curr_event is not None,
            "related_entities": _event_related_entities(prev_event, curr_event),
            "state_change_summary": _event_state_change_summary(prev_event, curr_event),
            "changed_observation_ids": _changed_observation_ids_for_event(
                event_id,
                previous_observations,
                current_observations,
            ),
            "claim_changed": bool(
                prev_sig["claim_bearing"] != curr_sig["claim_bearing"]
                or prev_sig["claim_step_indices"] != curr_sig["claim_step_indices"]
            ),
            "attribution_changed": bool(prev_sig["attributions"] != curr_sig["attributions"]),
            "anchor_status_changed": bool(
                prev_sig["anchor_status"] != curr_sig["anchor_status"] or prev_sig["anchor"] != curr_sig["anchor"]
            ),
        }
        if isinstance(review_context, dict):
            event_ctx = review_context.get(event_id)
            if event_ctx is not None:
                packet["review_context"] = event_ctx
        issue_packets.append(packet)

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for packet in issue_packets:
        severity = str(packet.get("severity") or "low")
        if severity in severity_counts:
            severity_counts[severity] += 1

    material_graph_change = any(
        [
            added_event_ids,
            removed_event_ids,
            changed_event_ids,
            sorted(set(curr_actors) - set(prev_actors)),
            sorted(set(prev_actors) - set(curr_actors)),
            sorted(set(curr_actions) - set(prev_actions)),
            sorted(set(prev_actions) - set(curr_actions)),
            sorted(set(curr_objects) - set(prev_objects)),
            sorted(set(prev_objects) - set(curr_objects)),
        ]
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "article": article,
        "revisions": {
            "same_article": (
                article.get("title") is not None
                and (
                    _safe_str(previous_snapshot_obj.get("title")) in {None, article.get("title")}
                    and _safe_str(current_snapshot_obj.get("title")) in {None, article.get("title")}
                )
            ),
            "previous": _revision_meta(previous_snapshot_obj),
            "current": _revision_meta(current_snapshot_obj),
        },
        "similarities": {
            "source_text": _similarity_summary(source_text_previous, source_text_current),
            "extraction_text": _similarity_summary(extraction_text_previous, extraction_text_current),
        },
        "state_delta_summary": {
            "available": bool(previous_state) and bool(current_state),
            "abstained": not (previous_state and current_state),
            "previous_sentence_unit_count": len(previous_units),
            "current_sentence_unit_count": len(current_units),
            "added_sentence_unit_ids": added_unit_ids,
            "removed_sentence_unit_ids": removed_unit_ids,
            "changed_sentence_unit_ids": changed_unit_ids,
            "previous_observation_count": len(previous_observations),
            "current_observation_count": len(current_observations),
            "added_observation_ids": added_observation_ids,
            "removed_observation_ids": removed_observation_ids,
            "changed_observation_ids": changed_observation_ids,
            "previous_event_candidate_count": len(previous_events),
            "current_event_candidate_count": len(current_events),
            "added_event_candidate_ids": added_event_ids,
            "removed_event_candidate_ids": removed_event_ids,
            "changed_event_candidate_ids": changed_event_ids,
            "changed_anchor_event_ids": changed_anchor_event_ids,
        },
        "extraction_delta_summary": {
            "available": bool(previous_state) and bool(current_state),
            "abstained": not (previous_state and current_state),
            "previous_event_count": len(previous_events),
            "current_event_count": len(current_events),
            "added_event_ids": added_event_ids,
            "removed_event_ids": removed_event_ids,
            "changed_event_ids": changed_event_ids,
            "previous_actor_count": len(prev_actors),
            "current_actor_count": len(curr_actors),
            "previous_action_count": len(prev_actions),
            "current_action_count": len(curr_actions),
            "previous_object_count": len(prev_objects),
            "current_object_count": len(curr_objects),
        },
        "graph_impact_summary": {
            "material_change": material_graph_change,
            "timeline": {
                "previous_event_count": len(prev_timeline_rows),
                "current_event_count": len(curr_timeline_rows),
                "changed_anchor_event_ids": changed_anchor_event_ids,
            },
            "actors": {
                "added": sorted(set(curr_actors) - set(prev_actors)),
                "removed": sorted(set(prev_actors) - set(curr_actors)),
            },
            "actions": {
                "added": sorted(set(curr_actions) - set(prev_actions)),
                "removed": sorted(set(prev_actions) - set(curr_actions)),
            },
            "objects": {
                "added": sorted(set(curr_objects) - set(prev_objects)),
                "removed": sorted(set(prev_objects) - set(curr_objects)),
            },
        },
        "epistemic_delta_summary": {
            "available": bool(previous_state) and bool(current_state),
            "abstained": not (previous_state and current_state),
            "previous_claim_bearing_event_count": len(prev_claim_ids),
            "current_claim_bearing_event_count": len(curr_claim_ids),
            "added_claim_bearing_event_ids": sorted(set(curr_claim_ids) - set(prev_claim_ids)),
            "removed_claim_bearing_event_ids": sorted(set(prev_claim_ids) - set(curr_claim_ids)),
            "previous_attribution_event_count": len(prev_attr_ids),
            "current_attribution_event_count": len(curr_attr_ids),
            "changed_attribution_event_ids": sorted(
                {
                    event_id
                    for event_id in packet_ids
                    if "epistemic" in _event_surface_diff(previous_events.get(event_id), current_events.get(event_id))[0]
                }
            ),
        },
        "issue_packets": issue_packets,
        "triage_dashboard": {
            "packet_counts": severity_counts,
            "top_packet_ids": [str(packet["packet_id"]) for packet in issue_packets[:5]],
            "highest_severity": (
                "high"
                if severity_counts["high"]
                else "medium"
                if severity_counts["medium"]
                else "low"
                if severity_counts["low"]
                else "none"
            ),
            "material_graph_change": material_graph_change,
        },
    }
