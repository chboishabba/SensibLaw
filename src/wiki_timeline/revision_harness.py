from __future__ import annotations

import json
import re
from typing import Any

from src.text.similarity import simhash, simhash_hamming_distance, token_jaccard_similarity

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


def _coalesce_snapshot(
    snapshot: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(snapshot, dict):
        return dict(snapshot)
    source_timeline = payload.get("source_timeline") if isinstance(payload, dict) else None
    if isinstance(source_timeline, dict) and isinstance(source_timeline.get("snapshot"), dict):
        return dict(source_timeline["snapshot"])
    return {}


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


def _extract_source_text(snapshot: dict[str, Any], payload: dict[str, Any] | None) -> str:
    wikitext = _norm_text(snapshot.get("wikitext"))
    if wikitext:
        return wikitext
    if isinstance(payload, dict):
        events = payload.get("events")
        if isinstance(events, list):
            event_texts = [_norm_text(ev.get("text")) for ev in events if isinstance(ev, dict)]
            joined = "\n".join(text for text in event_texts if text)
            if joined.strip():
                return joined
    return ""


def _extract_event_text(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    events = payload.get("events")
    if not isinstance(events, list):
        return ""
    texts = [_norm_text(ev.get("text")) for ev in events if isinstance(ev, dict)]
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


def _event_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    events = payload.get("events")
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
    if isinstance(actor, dict):
        return _safe_str(actor.get("resolved")) or _safe_str(actor.get("label"))
    return _safe_str(actor)


def _normalize_object(obj: Any) -> str | None:
    if isinstance(obj, dict):
        return _safe_str(obj.get("title")) or _safe_str(obj.get("text")) or _safe_str(obj.get("label"))
    return _safe_str(obj)


def _normalize_step_signature(step: Any) -> dict[str, Any] | None:
    if not isinstance(step, dict):
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
    if not isinstance(item, dict):
        return None
    return {
        "attributed_actor_id": _safe_str(item.get("attributed_actor_id")),
        "attribution_type": _safe_str(item.get("attribution_type")),
        "reporting_actor_id": _safe_str(item.get("reporting_actor_id")),
        "certainty_level": _safe_str(item.get("certainty_level")),
        "extraction_method": _safe_str(item.get("extraction_method")),
        "step_index": item.get("step_index"),
    }


def _event_signature(event: dict[str, Any]) -> dict[str, Any]:
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
    }


def _changed_event_ids(
    previous_events: dict[str, dict[str, Any]],
    current_events: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    prev_ids = set(previous_events)
    curr_ids = set(current_events)
    added = sorted(curr_ids - prev_ids)
    removed = sorted(prev_ids - curr_ids)
    changed: list[str] = []
    for event_id in sorted(prev_ids & curr_ids):
        if _stable_json(_event_signature(previous_events[event_id])) != _stable_json(
            _event_signature(current_events[event_id])
        ):
            changed.append(event_id)
    return added, removed, changed


def _collect_actor_surfaces(payload: dict[str, Any] | None) -> list[str]:
    events = _event_map(payload)
    values: list[str] = []
    for event in events.values():
        for actor in (event.get("actors") or []):
            value = _normalize_actor(actor)
            if value:
                values.append(value)
        for step in (event.get("steps") or []):
            if isinstance(step, dict):
                for subject in (step.get("subjects") or []):
                    value = _safe_str(subject)
                    if value:
                        values.append(value)
    return _sorted_unique(values)


def _collect_action_surfaces(payload: dict[str, Any] | None) -> list[str]:
    events = _event_map(payload)
    values: list[str] = []
    for event in events.values():
        action = _safe_str(event.get("action"))
        if action:
            values.append(action)
        for step in (event.get("steps") or []):
            if isinstance(step, dict):
                value = _safe_str(step.get("action"))
                if value:
                    values.append(value)
    return _sorted_unique(values)


def _collect_object_surfaces(payload: dict[str, Any] | None) -> list[str]:
    events = _event_map(payload)
    values: list[str] = []
    for event in events.values():
        for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            for obj in (event.get(field) or []):
                value = _normalize_object(obj)
                if value:
                    values.append(value)
        for step in (event.get("steps") or []):
            if isinstance(step, dict):
                for obj in (step.get("objects") or []):
                    value = _normalize_object(obj)
                    if value:
                        values.append(value)
    return _sorted_unique(values)


def _collect_claim_bearing_event_ids(payload: dict[str, Any] | None) -> list[str]:
    events = _event_map(payload)
    out: list[str] = []
    for event_id, event in events.items():
        if bool(event.get("claim_bearing")):
            out.append(event_id)
    return sorted(out)


def _collect_attribution_event_ids(payload: dict[str, Any] | None) -> list[str]:
    events = _event_map(payload)
    out: list[str] = []
    for event_id, event in events.items():
        attrs = event.get("attributions") or []
        if isinstance(attrs, list) and attrs:
            out.append(event_id)
    return sorted(out)


def _event_related_entities(previous_event: dict[str, Any] | None, current_event: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    for event in (previous_event, current_event):
        if not isinstance(event, dict):
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


def _event_surface_diff(previous_event: dict[str, Any] | None, current_event: dict[str, Any] | None) -> tuple[list[str], list[str]]:
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


def build_revision_comparison_report(
    *,
    previous_snapshot: dict[str, Any] | None = None,
    current_snapshot: dict[str, Any] | None = None,
    previous_payload: dict[str, Any] | None = None,
    current_payload: dict[str, Any] | None = None,
    review_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_snapshot_obj = _coalesce_snapshot(previous_snapshot, previous_payload)
    current_snapshot_obj = _coalesce_snapshot(current_snapshot, current_payload)
    article = _article_identity(previous_snapshot_obj, current_snapshot_obj, previous_payload, current_payload)

    previous_events = _event_map(previous_payload)
    current_events = _event_map(current_payload)
    added_event_ids, removed_event_ids, changed_event_ids = _changed_event_ids(previous_events, current_events)

    source_text_previous = _extract_source_text(previous_snapshot_obj, previous_payload)
    source_text_current = _extract_source_text(current_snapshot_obj, current_payload)
    extraction_text_previous = _extract_event_text(previous_payload)
    extraction_text_current = _extract_event_text(current_payload)

    prev_actors = _collect_actor_surfaces(previous_payload)
    curr_actors = _collect_actor_surfaces(current_payload)
    prev_actions = _collect_action_surfaces(previous_payload)
    curr_actions = _collect_action_surfaces(current_payload)
    prev_objects = _collect_object_surfaces(previous_payload)
    curr_objects = _collect_object_surfaces(current_payload)
    prev_claim_ids = _collect_claim_bearing_event_ids(previous_payload)
    curr_claim_ids = _collect_claim_bearing_event_ids(current_payload)
    prev_attr_ids = _collect_attribution_event_ids(previous_payload)
    curr_attr_ids = _collect_attribution_event_ids(current_payload)

    packet_ids = sorted(set(added_event_ids + removed_event_ids + changed_event_ids))
    issue_packets: list[dict[str, Any]] = []
    for event_id in packet_ids:
        prev_event = previous_events.get(event_id)
        curr_event = current_events.get(event_id)
        surfaces, reasons = _event_surface_diff(prev_event, curr_event)
        packet = {
            "packet_id": f"packet:{article.get('title') or 'article'}:{event_id}",
            "event_id": event_id,
            "severity": _severity_for_surfaces(surfaces),
            "surfaces": surfaces,
            "summary": _packet_summary(reasons),
            "previous_event_present": prev_event is not None,
            "current_event_present": curr_event is not None,
            "related_entities": _event_related_entities(prev_event, curr_event),
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
        "extraction_delta_summary": {
            "available": bool(previous_payload) and bool(current_payload),
            "abstained": not (previous_payload and current_payload),
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
            "available": bool(previous_payload) and bool(current_payload),
            "abstained": not (previous_payload and current_payload),
            "previous_claim_bearing_event_count": len(prev_claim_ids),
            "current_claim_bearing_event_count": len(curr_claim_ids),
            "added_claim_bearing_event_ids": sorted(set(curr_claim_ids) - set(prev_claim_ids)),
            "removed_claim_bearing_event_ids": sorted(set(prev_claim_ids) - set(curr_claim_ids)),
            "previous_attribution_event_count": len(prev_attr_ids),
            "current_attribution_event_count": len(curr_attr_ids),
            "changed_attribution_event_ids": sorted(
                set(
                    event_id
                    for event_id in packet_ids
                    if "epistemic"
                    in _event_surface_diff(previous_events.get(event_id), current_events.get(event_id))[0]
                )
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
