from __future__ import annotations

import json
from typing import Any


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _norm_determiner(value: Any) -> str:
    text = _norm_text(value)
    if not text:
        return text
    parts = [part for part in text.split(" ") if part]
    if len(parts) <= 1:
        return text
    first = parts[0]
    if first in {"the", "a", "an"}:
        return " ".join(parts[1:])
    return text


def _sorted_unique(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value).strip()})


def _normalize_anchor(raw: Any) -> dict[str, Any]:
    return {
        "year": int(raw.get("year") or 0) if isinstance(raw, dict) else 0,
        "month": int(raw["month"]) if isinstance(raw, dict) and raw.get("month") is not None else None,
        "day": int(raw["day"]) if isinstance(raw, dict) and raw.get("day") is not None else None,
        "precision": str(raw.get("precision") or "year") if isinstance(raw, dict) else "year",
        "text": str(raw.get("text") or "") if isinstance(raw, dict) else "",
        "kind": str(raw.get("kind") or "") if isinstance(raw, dict) else "",
    }


def _same_anchor(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        int(a.get("year") or 0) == int(b.get("year") or 0)
        and (a.get("month") if a.get("month") is not None else -1) == (b.get("month") if b.get("month") is not None else -1)
        and (a.get("day") if a.get("day") is not None else -1) == (b.get("day") if b.get("day") is not None else -1)
    )


def _key_for_anchor(anchor: dict[str, Any]) -> int:
    return (int(anchor.get("year") or 9999) * 10_000) + ((anchor.get("month") if anchor.get("month") is not None else 99) * 100) + (
        anchor.get("day") if anchor.get("day") is not None else 99
    )


def _fact_identity_key(row: dict[str, Any]) -> str:
    anchor = row.get("anchor") or {}
    payload = {
        "event_id": str(row.get("event_id") or ""),
        "anchor": {
            "year": int(anchor.get("year") or 0),
            "month": anchor.get("month"),
            "day": anchor.get("day"),
            "precision": str(anchor.get("precision") or ""),
            "kind": str(anchor.get("kind") or ""),
        },
        "action": _norm_text(row.get("action")),
        "negation_kind": _norm_text((row.get("negation") or {}).get("kind") if isinstance(row.get("negation"), dict) else ""),
        "subjects": _sorted_unique([_norm_determiner(v) for v in row.get("subjects") or []]),
        "objects": _sorted_unique([_norm_determiner(v) for v in row.get("objects") or []]),
        "chain_kinds": _sorted_unique([_norm_text(v) for v in row.get("chain_kinds") or []]),
    }
    return json.dumps(payload, sort_keys=True)


def _coalesce_fact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    key_to_canon: dict[str, dict[str, Any]] = {}
    fact_id_alias: dict[str, str] = {}
    for row in rows:
        key = _fact_identity_key(row)
        current = key_to_canon.get(key)
        if current is None:
            base = dict(row)
            base["prev_fact_ids"] = _sorted_unique(base.get("prev_fact_ids") or [])
            base["next_fact_ids"] = _sorted_unique(base.get("next_fact_ids") or [])
            base["chain_kinds"] = _sorted_unique(base.get("chain_kinds") or [])
            key_to_canon[key] = base
            fact_id_alias[str(row.get("fact_id") or "")] = str(base.get("fact_id") or "")
            continue
        fact_id_alias[str(row.get("fact_id") or "")] = str(current.get("fact_id") or "")
        current["prev_fact_ids"] = _sorted_unique([*(current.get("prev_fact_ids") or []), *(row.get("prev_fact_ids") or [])])
        current["next_fact_ids"] = _sorted_unique([*(current.get("next_fact_ids") or []), *(row.get("next_fact_ids") or [])])
        current["chain_kinds"] = _sorted_unique([*(current.get("chain_kinds") or []), *(row.get("chain_kinds") or [])])

    out = list(key_to_canon.values())
    canon_ids = {str(row.get("fact_id") or "") for row in out}
    for row in out:
        self_id = str(row.get("fact_id") or "")
        row["prev_fact_ids"] = [
            item
            for item in _sorted_unique([fact_id_alias.get(str(v), str(v)) for v in row.get("prev_fact_ids") or []])
            if item != self_id and item in canon_ids
        ]
        row["next_fact_ids"] = [
            item
            for item in _sorted_unique([fact_id_alias.get(str(v), str(v)) for v in row.get("next_fact_ids") or []])
            if item != self_id and item in canon_ids
        ]
        row["chain_kinds"] = _sorted_unique(row.get("chain_kinds") or [])
    return out


def _coerce_fact_row(
    raw: dict[str, Any],
    section_by_event: dict[str, str],
    text_by_event: dict[str, str],
    event_anchor_by_event: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    mention_anchor = _normalize_anchor(raw.get("anchor"))
    event_id = str(raw.get("event_id") or "")
    event_anchor = event_anchor_by_event.get(event_id)
    mention_valid = int(mention_anchor.get("year") or 0) > 0
    use_event = (not mention_valid) and bool(event_anchor and int(event_anchor.get("year") or 0) > 0)
    primary_anchor = mention_anchor if mention_valid else (event_anchor or mention_anchor)
    event_out = event_anchor if event_anchor and not _same_anchor(primary_anchor, event_anchor) else None
    negation = raw.get("negation") if isinstance(raw.get("negation"), dict) and isinstance(raw.get("negation", {}).get("kind"), str) else None
    return {
        "fact_id": str(raw.get("fact_id") or ""),
        "event_id": event_id,
        "anchor": primary_anchor,
        "event_anchor": event_out,
        "anchor_source": "event" if use_event else "mention",
        "party": str(raw.get("party") or ""),
        "subjects": [str(value) for value in raw.get("subjects") or [] if str(value).strip()],
        "action": str(raw.get("action")) if isinstance(raw.get("action"), str) else None,
        "negation": {
            "kind": str(negation.get("kind")),
            "scope": negation.get("scope"),
            "source": negation.get("source"),
        } if negation else None,
        "objects": [str(value) for value in raw.get("objects") or [] if str(value).strip()],
        "purpose": str(raw.get("purpose")) if isinstance(raw.get("purpose"), str) else None,
        "text": str(raw.get("text") or text_by_event.get(event_id) or ""),
        "section": str(section_by_event.get(event_id) or ""),
        "prev_fact_ids": [str(value) for value in raw.get("prev_fact_ids") or [] if str(value).strip()],
        "next_fact_ids": [str(value) for value in raw.get("next_fact_ids") or [] if str(value).strip()],
        "chain_kinds": [str(value) for value in raw.get("chain_kinds") or [] if str(value).strip()],
    }


def _synthesize_facts_from_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        actors = event.get("actors") or []
        objects = event.get("objects") or []
        steps = event.get("steps") if isinstance(event.get("steps"), list) and event.get("steps") else [
            {
                "action": event.get("action"),
                "subjects": [
                    str(actor.get("resolved") or actor.get("label"))
                    for actor in actors
                    if isinstance(actor, dict) and str(actor.get("role") or "") != "requester"
                ],
                "objects": [str(obj.get("title")) for obj in objects if isinstance(obj, dict)],
                "purpose": event.get("purpose"),
            }
        ]
        event_rows: list[dict[str, Any]] = []
        fact_id_by_step: dict[int, str] = {}
        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            subjects = [str(value) for value in step.get("subjects") or [] if str(value).strip()]
            objects_out = [str(value) for value in step.get("objects") or [] if str(value).strip()]
            action = str(step.get("action")) if isinstance(step.get("action"), str) else None
            if not action and not subjects and not objects_out:
                continue
            fact_id = f"{event.get('event_id')}:f{str(idx + 1).zfill(2)}"
            row = {
                "fact_id": fact_id,
                "event_id": str(event.get("event_id") or ""),
                "step_index": idx,
                "anchor": event.get("anchor") or {},
                "party": str(event.get("party") or ""),
                "subjects": subjects,
                "action": action,
                "negation": step.get("negation") if isinstance(step.get("negation"), dict) and isinstance(step.get("negation", {}).get("kind"), str) else None,
                "objects": objects_out,
                "purpose": str(step.get("purpose")) if isinstance(step.get("purpose"), str) else event.get("purpose"),
                "text": str(event.get("text") or ""),
                "prev_fact_ids": [],
                "next_fact_ids": [],
                "chain_kinds": [],
            }
            fact_id_by_step[idx] = fact_id
            event_rows.append(row)
        by_fact_id = {str(row["fact_id"]): row for row in event_rows}
        for idx in range(len(event_rows) - 1):
            current = event_rows[idx]
            nxt = event_rows[idx + 1]
            current["next_fact_ids"] = list(dict.fromkeys([*(current.get("next_fact_ids") or []), str(nxt["fact_id"])]))
            current["chain_kinds"] = list(dict.fromkeys([*(current.get("chain_kinds") or []), "sequence"]))
            nxt["prev_fact_ids"] = list(dict.fromkeys([*(nxt.get("prev_fact_ids") or []), str(current["fact_id"])]))
        if isinstance(event.get("chains"), list):
            for chain in event["chains"]:
                if not isinstance(chain, dict):
                    continue
                from_step = chain.get("from_step")
                to_step = chain.get("to_step")
                if not isinstance(from_step, int) or not isinstance(to_step, int):
                    continue
                from_fact = fact_id_by_step.get(from_step)
                to_fact = fact_id_by_step.get(to_step)
                if not from_fact or not to_fact:
                    continue
                from_row = by_fact_id.get(from_fact)
                to_row = by_fact_id.get(to_fact)
                if not from_row or not to_row:
                    continue
                kind = str(chain.get("kind") or "sequence")
                from_row["next_fact_ids"] = list(dict.fromkeys([*(from_row.get("next_fact_ids") or []), to_fact]))
                from_row["chain_kinds"] = list(dict.fromkeys([*(from_row.get("chain_kinds") or []), kind]))
                to_row["prev_fact_ids"] = list(dict.fromkeys([*(to_row.get("prev_fact_ids") or []), from_fact]))
        rows.extend(event_rows)
    return rows


def _coerce_proposition(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    proposition_id = str(raw.get("proposition_id") or "")
    event_id = str(raw.get("event_id") or "")
    proposition_kind = str(raw.get("proposition_kind") or "")
    predicate_key = str(raw.get("predicate_key") or "")
    if not proposition_id or not event_id or not proposition_kind or not predicate_key:
        return None
    negation = raw.get("negation") if isinstance(raw.get("negation"), dict) and isinstance(raw.get("negation", {}).get("kind"), str) else None
    return {
        "proposition_id": proposition_id,
        "event_id": event_id,
        "proposition_kind": proposition_kind,
        "predicate_key": predicate_key,
        "negation": {
            "kind": str(negation.get("kind")),
            "scope": negation.get("scope"),
            "source": negation.get("source"),
        } if negation else None,
        "source_fact_id": str(raw.get("source_fact_id")) if isinstance(raw.get("source_fact_id"), str) else None,
        "source_signal": str(raw.get("source_signal")) if isinstance(raw.get("source_signal"), str) else None,
        "anchor_text": str(raw.get("anchor_text")) if isinstance(raw.get("anchor_text"), str) else None,
        "arguments": [
            {"role": str(arg.get("role")), "value": str(arg.get("value"))}
            for arg in raw.get("arguments") or []
            if isinstance(arg, dict) and isinstance(arg.get("role"), str) and isinstance(arg.get("value"), str)
        ],
        "receipts": [
            {"kind": str(receipt.get("kind")), "value": str(receipt.get("value"))}
            for receipt in raw.get("receipts") or []
            if isinstance(receipt, dict) and isinstance(receipt.get("kind"), str) and isinstance(receipt.get("value"), str)
        ],
    }


def _coerce_proposition_link(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    link_id = str(raw.get("link_id") or "")
    event_id = str(raw.get("event_id") or "")
    source_proposition_id = str(raw.get("source_proposition_id") or "")
    target_proposition_id = str(raw.get("target_proposition_id") or "")
    link_kind = str(raw.get("link_kind") or "")
    if not link_id or not event_id or not source_proposition_id or not target_proposition_id or not link_kind:
        return None
    return {
        "link_id": link_id,
        "event_id": event_id,
        "source_proposition_id": source_proposition_id,
        "target_proposition_id": target_proposition_id,
        "link_kind": link_kind,
        "receipts": [
            {"kind": str(receipt.get("kind")), "value": str(receipt.get("value"))}
            for receipt in raw.get("receipts") or []
            if isinstance(receipt, dict) and isinstance(receipt.get("kind"), str) and isinstance(receipt.get("value"), str)
        ],
    }


def build_fact_timeline_projection(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events") or []
    section_by_event = {str(event.get("event_id") or ""): str(event.get("section") or "") for event in events if isinstance(event, dict)}
    text_by_event = {str(event.get("event_id") or ""): str(event.get("text") or "") for event in events if isinstance(event, dict)}
    event_anchor_by_event = {
        str(event.get("event_id") or ""): _normalize_anchor(event.get("anchor"))
        for event in events
        if isinstance(event, dict)
    }

    fact_row_source = "native_fact_timeline"
    if isinstance(payload.get("fact_timeline"), list) and payload.get("fact_timeline"):
        raw_facts = payload.get("fact_timeline") or []
        fact_row_source = "native_fact_timeline"
    else:
        nested = []
        for event in events:
            if isinstance(event, dict) and isinstance(event.get("timeline_facts"), list):
                nested.extend(event.get("timeline_facts") or [])
        if nested:
            raw_facts = nested
            fact_row_source = "nested_event_timeline_facts"
        else:
            raw_facts = _synthesize_facts_from_events(payload)
            fact_row_source = "synthesized_from_steps"

    facts = _coalesce_fact_rows(
        sorted(
            [
                _coerce_fact_row(fact, section_by_event, text_by_event, event_anchor_by_event)
                for fact in raw_facts
                if isinstance(fact, dict) and str(fact.get("fact_id") or "") and str(fact.get("event_id") or "")
            ],
            key=lambda row: (_key_for_anchor(row["anchor"]), str(row.get("fact_id") or "")),
        )
    )
    propositions = [
        row
        for row in (_coerce_proposition(item) for item in payload.get("propositions") or [])
        if row is not None
    ]
    proposition_links = [
        row
        for row in (_coerce_proposition_link(item) for item in payload.get("proposition_links") or [])
        if row is not None
    ]

    return {
        "root_actor": payload.get("root_actor") or {"label": "", "surname": ""},
        "parser": payload.get("parser"),
        "facts": facts,
        "propositions": propositions,
        "proposition_links": proposition_links,
        "diagnostics": {
            "event_count": len(events),
            "fact_row_source": fact_row_source,
            "raw_fact_rows": len(raw_facts),
            "output_fact_rows": len(facts),
        },
    }
