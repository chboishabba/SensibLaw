from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import io
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

_THIS_DIR = Path(__file__).resolve().parent
_SENSIBLAW_ROOT = _THIS_DIR.parents[1]
if str(_SENSIBLAW_ROOT) not in sys.path:
    sys.path.insert(0, str(_SENSIBLAW_ROOT))

from scripts import wiki_timeline_extract as timeline_extract  # noqa: E402
from scripts.wiki_timeline_aoo_extract import main as wiki_timeline_aoo_main  # noqa: E402


STATE_SCHEMA_VERSION = "wiki_article_state_v0_1"
SENTENCE_SURFACE_SCHEMA_VERSION = "wiki_random_article_sentences_v0_1"

_REGIME_NARRATIVE_MARKERS = (
    " said ",
    " reported ",
    " asked ",
    " called ",
    " met ",
    " arrived ",
    " launched ",
    " established ",
    " performed ",
    " ordered ",
    " in ",
    " on ",
    " after ",
    " before ",
    " later ",
)
_REGIME_DESCRIPTIVE_MARKERS = (
    " is ",
    " are ",
    " was ",
    " were ",
    " has ",
    " have ",
    " consists of ",
    " includes ",
    " contains ",
    " based in ",
    " designed to ",
    " known for ",
)
_REGIME_FORMAL_MARKERS = (
    " theorem",
    " lemma",
    " proposition",
    " corollary",
    " proof",
    " if and only if",
    " iff",
    " let ",
    " suppose ",
    " there exists",
    " continuous",
    " compact",
    " operator",
    " function",
    " ∀",
    " ∃",
    " ⇒",
    " →",
    " ↦",
    " ∫",
)


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_str(value: Any) -> str | None:
    text = _norm_text(value)
    return text or None


def _stable_digest(*parts: Any) -> str:
    payload = "\n".join(_norm_text(part) for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _stable_observation_id(
    *,
    event_id: str,
    predicate: str,
    object_text: str | None = None,
    step_index: int | None = None,
    anchor_status: str | None = None,
) -> str:
    return (
        "obs:"
        + _stable_digest(
            event_id,
            predicate,
            object_text or "",
            step_index if step_index is not None else "",
            anchor_status or "",
        )
    )


def _run_quiet(fn: Any, argv: list[str]) -> int:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        return int(fn(argv))


def coalesce_snapshot(
    snapshot: Mapping[str, Any] | None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    if isinstance(payload, Mapping):
        source_timeline = payload.get("source_timeline")
        if isinstance(source_timeline, Mapping) and isinstance(source_timeline.get("snapshot"), Mapping):
            return dict(source_timeline["snapshot"])
        source_snapshot = payload.get("snapshot")
        if isinstance(source_snapshot, Mapping):
            return dict(source_snapshot)
        article = payload.get("article")
        source_text = payload.get("source_text")
        if payload.get("schema_version") == STATE_SCHEMA_VERSION and isinstance(article, Mapping):
            out = dict(article)
            if isinstance(source_text, Mapping) and isinstance(source_text.get("wikitext"), str):
                out["wikitext"] = source_text.get("wikitext")
            return out
    return {}


def _article_identity(snapshot: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_entity = payload.get("source_entity") if isinstance(payload, Mapping) else None
    return {
        "wiki": snapshot.get("wiki") or (source_entity.get("wiki") if isinstance(source_entity, Mapping) else None),
        "title": snapshot.get("title") or (source_entity.get("title") if isinstance(source_entity, Mapping) else None),
        "pageid": snapshot.get("pageid"),
        "revid": snapshot.get("revid"),
        "rev_timestamp": snapshot.get("rev_timestamp"),
        "source_url": snapshot.get("source_url") or (source_entity.get("url") if isinstance(source_entity, Mapping) else None),
        "fetched_at": snapshot.get("fetched_at"),
    }


def _normalize_actor(actor: Any) -> str | None:
    if isinstance(actor, Mapping):
        return _safe_str(actor.get("resolved")) or _safe_str(actor.get("label")) or _safe_str(actor.get("text"))
    return _safe_str(actor)


def _normalize_object(obj: Any) -> str | None:
    if isinstance(obj, Mapping):
        return _safe_str(obj.get("title")) or _safe_str(obj.get("text")) or _safe_str(obj.get("label"))
    return _safe_str(obj)


def _contains_any(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def _derive_regime_vector(
    *,
    sentence_units: Iterable[Mapping[str, Any]],
    event_candidates: Iterable[Mapping[str, Any]],
) -> dict[str, float]:
    narrative = 0.0
    descriptive = 0.0
    formal = 0.0

    event_by_id = {
        str(event.get("event_id") or ""): event
        for event in event_candidates
        if isinstance(event, Mapping)
    }

    for sentence in sentence_units:
        if not isinstance(sentence, Mapping):
            continue
        text = str(sentence.get("text") or "").lower()
        event_id = str(sentence.get("event_id") or sentence.get("unit_id") or "")
        anchor_status = str(sentence.get("anchor_status") or "none")
        event = event_by_id.get(event_id)

        if anchor_status == "explicit":
            narrative += 1.5
        elif anchor_status == "weak":
            narrative += 0.75

        if isinstance(event, Mapping):
            if _safe_str(event.get("action")):
                narrative += 1.25
            if bool(event.get("claim_bearing")):
                narrative += 0.5

        if _contains_any(text, _REGIME_NARRATIVE_MARKERS):
            narrative += 0.5
        if _contains_any(text, _REGIME_DESCRIPTIVE_MARKERS) or ":" in text or text.count(",") >= 4 or ";" in text:
            descriptive += 1.0
        if _contains_any(text, _REGIME_FORMAL_MARKERS):
            formal += 1.5

    total = narrative + descriptive + formal
    if total <= 0.0:
        return {"narrative": 1 / 3, "descriptive": 1 / 3, "formal": 1 / 3}
    return {
        "narrative": round(narrative / total, 6),
        "descriptive": round(descriptive / total, 6),
        "formal": round(formal / total, 6),
    }


def _anchor_status_from_anchor(anchor: Mapping[str, Any] | None) -> str:
    if not isinstance(anchor, Mapping):
        return "none"
    kind = _safe_str(anchor.get("kind")) or "weak"
    if kind in {"explicit", "mention"}:
        return "explicit"
    return "weak"


def _anchor_rank(anchor: Mapping[str, Any]) -> tuple[int, int, int, int]:
    status = _anchor_status_from_anchor(anchor)
    precision = _safe_str(anchor.get("precision")) or "year"
    precision_rank = {"day": 3, "month": 2, "year": 1}.get(precision, 0)
    status_rank = {"explicit": 2, "weak": 1, "none": 0}.get(status, 0)
    year = int(anchor.get("year") or 0)
    month = int(anchor.get("month") or 0)
    day = int(anchor.get("day") or 0)
    return (status_rank, precision_rank, year, month * 32 + day)


def _anchor_json(anchor: Any) -> dict[str, Any] | None:
    if hasattr(anchor, "to_json"):
        return dict(anchor.to_json())
    if isinstance(anchor, Mapping):
        return dict(anchor)
    return None


def _dedupe_anchors(anchors: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for anchor in anchors:
        key = (
            anchor.get("year"),
            anchor.get("month"),
            anchor.get("day"),
            anchor.get("precision"),
            anchor.get("kind"),
            anchor.get("text"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(anchor))
    return out


def _collect_sentence_anchor_candidates(
    *,
    section: str,
    sentence: str,
    sentence_index: int,
    section_anchor: Mapping[str, Any] | None,
    section_heading_emitted: dict[str, bool],
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    anchor = _anchor_json(timeline_extract._parse_anchor(sentence))
    if anchor:
        anchors.append(anchor)

    if not anchors and section_anchor is not None and not section_heading_emitted.get(section, False):
        if sentence_index == 0:
            anchors.append(dict(section_anchor))
            section_heading_emitted[section] = True

    for candidate in timeline_extract._parse_inline_anchors(sentence):
        candidate_json = _anchor_json(candidate)
        if candidate_json:
            anchors.append(candidate_json)
    for candidate in timeline_extract._parse_inline_year_range_anchors(sentence):
        candidate_json = _anchor_json(candidate)
        if candidate_json:
            anchors.append(candidate_json)
    if not anchors:
        for candidate in timeline_extract._parse_inline_weak_years(sentence):
            candidate_json = _anchor_json(candidate)
            if candidate_json:
                anchors.append(candidate_json)
                break
    for candidate in timeline_extract._parse_special_event_anchors(sentence):
        candidate_json = _anchor_json(candidate)
        if candidate_json:
            anchors.append(candidate_json)

    deduped = _dedupe_anchors(anchors)
    if not deduped:
        return []

    adjusted = timeline_extract._apply_lead_anchor_preference(
        section,
        sentence,
        [timeline_extract.DateAnchor(**anchor) for anchor in deduped],
    )
    return _dedupe_anchors(_anchor_json(anchor) for anchor in adjusted if _anchor_json(anchor))


def _iter_sentence_units(wikitext: str, *, max_sentences: int) -> Iterable[dict[str, Any]]:
    section_heading_emitted: dict[str, bool] = {}
    seen_sentence_keys: dict[str, int] = defaultdict(int)
    order_index = 0
    for section, para_wt in timeline_extract._iter_section_paragraphs(wikitext):
        plain = timeline_extract._strip_wikitext(para_wt)
        plain = timeline_extract._collapse_ws(timeline_extract._strip_refs(plain))
        if not plain:
            continue
        sentences = timeline_extract._split_sentences(plain)
        para_links = timeline_extract._wikitext_links(para_wt)[:120]
        section_anchor = _anchor_json(timeline_extract._parse_section_anchor(section))
        for sentence_index, sentence in enumerate(sentences):
            sentence = timeline_extract._cleanup_sentence_text(sentence)
            if not sentence:
                continue
            if timeline_extract._looks_like_media_caption(sentence):
                continue
            if timeline_extract._looks_like_template_residue(sentence):
                continue
            order_index += 1
            sentence_key = _stable_digest(section, sentence)
            seen_sentence_keys[sentence_key] += 1
            unit_id = f"art:{sentence_key}:{seen_sentence_keys[sentence_key]:02d}"
            anchor_candidates = _collect_sentence_anchor_candidates(
                section=section,
                sentence=sentence,
                sentence_index=sentence_index,
                section_anchor=section_anchor,
                section_heading_emitted=section_heading_emitted,
            )
            primary_anchor = max(anchor_candidates, key=_anchor_rank) if anchor_candidates else None
            yield {
                "unit_id": unit_id,
                "event_id": unit_id,
                "order_index": order_index,
                "section": section,
                "text": sentence,
                "links": timeline_extract._links_in_sentence(para_wt, sentence)[:50],
                "links_para": para_links,
                "anchor": primary_anchor,
                "anchor_candidates": anchor_candidates,
                "anchor_status": _anchor_status_from_anchor(primary_anchor),
                "ordering_basis": "source_text_order",
                "lane": "article_sentence",
            }
            if order_index >= int(max_sentences):
                return


def build_article_sentence_surface(
    snapshot: Mapping[str, Any],
    *,
    max_sentences: int = 400,
) -> dict[str, Any]:
    wikitext = str(snapshot.get("wikitext") or "")
    if not wikitext.strip():
        raise ValueError("snapshot has no wikitext")

    sentence_units = list(_iter_sentence_units(wikitext, max_sentences=max_sentences))
    article = _article_identity(snapshot)
    return {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "snapshot": article,
        "surface": {
            "kind": SENTENCE_SURFACE_SCHEMA_VERSION,
            "max_sentences": int(max_sentences),
        },
        "events": sentence_units,
        "notes": [
            "This surface preserves article-wide cleaned sentence rows for bounded AAO ingestion.",
            "Rows are sentence-local and non-authoritative; they exist to score broad ingest coverage.",
            "Timeline and revision views are projections over the same canonical wiki state.",
        ],
    }


def _run_aoo_surface(
    article_surface: Mapping[str, Any],
    *,
    max_events: int,
    no_spacy: bool,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wiki-article-state-") as tmpdir:
        tmp_root = Path(tmpdir)
        article_surface_path = tmp_root / "article_surface.json"
        article_aoo_path = tmp_root / "article_aoo.json"
        article_surface_path.write_text(
            json.dumps(article_surface, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        argv = [
            "--timeline",
            str(article_surface_path),
            "--out",
            str(article_aoo_path),
            "--max-events",
            str(max(1, int(max_events))),
            "--no-db",
        ]
        if no_spacy:
            argv.append("--no-spacy")
        exit_code = _run_quiet(wiki_timeline_aoo_main, argv)
        if exit_code != 0:
            raise RuntimeError(
                f"wiki_timeline_aoo_extract failed for {article_surface.get('snapshot', {}).get('title')}"
            )
        return _load_json(article_aoo_path)


def _extract_event_candidates(
    payload: Mapping[str, Any] | None,
    *,
    sentence_units: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    events = payload.get("events") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        return []
    sentence_by_id = {
        str(unit.get("event_id") or unit.get("unit_id")): unit
        for unit in sentence_units
        if isinstance(unit, Mapping)
    }
    out: list[dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, Mapping):
            continue
        event_id = _safe_str(event.get("event_id")) or f"event:{index:04d}"
        unit = sentence_by_id.get(event_id)
        if isinstance(unit, Mapping) and isinstance(unit.get("anchor"), Mapping):
            anchor = dict(unit["anchor"])
        elif isinstance(event.get("anchor"), Mapping):
            anchor = dict(event["anchor"])
        else:
            anchor = None
        if isinstance(unit, Mapping):
            anchor_candidates = [dict(item) for item in unit.get("anchor_candidates") or [] if isinstance(item, Mapping)]
            order_index = int(unit.get("order_index") or index)
            sentence_unit_id = str(unit.get("unit_id") or event_id)
            ordering_basis = str(unit.get("ordering_basis") or "source_text_order")
        else:
            anchor_candidates = [dict(item) for item in event.get("anchor_candidates") or [] if isinstance(item, Mapping)]
            order_index = index
            sentence_unit_id = event_id
            ordering_basis = "source_text_order"
        out.append(
            {
                **dict(event),
                "event_id": event_id,
                "sentence_unit_id": sentence_unit_id,
                "order_index": order_index,
                "ordering_basis": ordering_basis,
                "anchor": anchor,
                "anchor_candidates": anchor_candidates,
                "anchor_status": _anchor_status_from_anchor(anchor),
            }
        )
    return out


def _observation_record(
    *,
    event: Mapping[str, Any],
    predicate: str,
    object_text: str | None,
    sentence_unit_id: str,
    source_text: str,
    step_index: int | None = None,
) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    anchor_status = str(event.get("anchor_status") or "none")
    return {
        "observation_id": _stable_observation_id(
            event_id=event_id,
            predicate=predicate,
            object_text=object_text,
            step_index=step_index,
            anchor_status=anchor_status,
        ),
        "event_id": event_id,
        "sentence_unit_id": sentence_unit_id,
        "predicate": predicate,
        "object_text": object_text,
        "anchor_status": anchor_status,
        "status": "captured",
        "source_text": source_text,
        "step_index": step_index,
    }


def build_observations_from_event_candidates(event_candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for event in event_candidates:
        if not isinstance(event, Mapping):
            continue
        sentence_unit_id = str(event.get("sentence_unit_id") or event.get("event_id") or "")
        source_text = str(event.get("text") or "")
        for actor in event.get("actors") or []:
            value = _normalize_actor(actor)
            if value:
                observations.append(
                    _observation_record(
                        event=event,
                        predicate="actor",
                        object_text=value,
                        sentence_unit_id=sentence_unit_id,
                        source_text=source_text,
                    )
                )
        action = _safe_str(event.get("action"))
        if action:
            observations.append(
                _observation_record(
                    event=event,
                    predicate="performed_action",
                    object_text=action,
                    sentence_unit_id=sentence_unit_id,
                    source_text=source_text,
                )
            )
        for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects"):
            for obj in event.get(field) or []:
                value = _normalize_object(obj)
                if value:
                    observations.append(
                        _observation_record(
                            event=event,
                            predicate="acted_on",
                            object_text=value,
                            sentence_unit_id=sentence_unit_id,
                            source_text=source_text,
                        )
                    )
        if event.get("claim_bearing"):
            observations.append(
                _observation_record(
                    event=event,
                    predicate="claimed",
                    object_text=_safe_str(event.get("text")) or _safe_str(event.get("action")),
                    sentence_unit_id=sentence_unit_id,
                    source_text=source_text,
                )
            )
        for attr_index, attr in enumerate(event.get("attributions") or []):
            if not isinstance(attr, Mapping):
                continue
            object_text = _safe_str(attr.get("attribution_type")) or _safe_str(attr.get("attributed_actor_id"))
            if object_text:
                observations.append(
                    _observation_record(
                        event=event,
                        predicate="communicated",
                        object_text=object_text,
                        sentence_unit_id=sentence_unit_id,
                        source_text=source_text,
                        step_index=int(attr.get("step_index")) if isinstance(attr.get("step_index"), int) else attr_index,
                    )
                )
        anchor = event.get("anchor")
        if isinstance(anchor, Mapping):
            if anchor.get("day") is not None:
                anchor_text = (
                    f"{int(anchor.get('year') or 0):04d}-"
                    f"{int(anchor.get('month') or 0):02d}-"
                    f"{int(anchor.get('day') or 0):02d}"
                )
            elif anchor.get("month") is not None:
                anchor_text = f"{int(anchor.get('year') or 0):04d}-{int(anchor.get('month') or 0):02d}"
            else:
                anchor_text = str(anchor.get("year"))
            observations.append(
                _observation_record(
                    event=event,
                    predicate="event_date",
                    object_text=anchor_text,
                    sentence_unit_id=sentence_unit_id,
                    source_text=source_text,
                )
            )
    return observations


def build_timeline_projection(event_candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        [dict(event) for event in event_candidates if isinstance(event, Mapping)],
        key=lambda event: (int(event.get("order_index") or 0), str(event.get("event_id") or "")),
    )
    return [
        {
            "event_id": str(event.get("event_id") or ""),
            "sentence_unit_id": str(event.get("sentence_unit_id") or event.get("event_id") or ""),
            "order_index": int(event.get("order_index") or 0),
            "ordering_basis": str(event.get("ordering_basis") or "source_text_order"),
            "anchor_status": str(event.get("anchor_status") or "none"),
            "anchor": dict(event.get("anchor")) if isinstance(event.get("anchor"), Mapping) else None,
            "action": _safe_str(event.get("action")),
            "claim_bearing": bool(event.get("claim_bearing")),
            "text": str(event.get("text") or ""),
            "actor_count": len(event.get("actors") or []) if isinstance(event.get("actors"), list) else 0,
            "object_count": sum(
                len(event.get(field) or [])
                for field in ("objects", "entity_objects", "modifier_objects", "numeric_objects")
                if isinstance(event.get(field), list)
            ),
        }
        for event in ordered
    ]


def build_wiki_article_state(
    snapshot: Mapping[str, Any],
    *,
    max_sentences: int = 400,
    max_events: int | None = None,
    no_spacy: bool = False,
) -> dict[str, Any]:
    article_surface = build_article_sentence_surface(snapshot, max_sentences=max_sentences)
    sentence_units = [dict(row) for row in article_surface.get("events") or [] if isinstance(row, Mapping)]
    aoo_payload = _run_aoo_surface(
        article_surface,
        max_events=max_events if max_events is not None else max_sentences,
        no_spacy=no_spacy,
    )
    event_candidates = _extract_event_candidates(aoo_payload, sentence_units=sentence_units)
    observations = build_observations_from_event_candidates(event_candidates)
    timeline_projection = build_timeline_projection(event_candidates)
    article = _article_identity(snapshot, aoo_payload)
    wikitext = str(snapshot.get("wikitext") or "")
    anchor_counter = Counter(str(row.get("anchor_status") or "none") for row in timeline_projection)
    regime = _derive_regime_vector(sentence_units=sentence_units, event_candidates=event_candidates)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "article": article,
        "source_text": {
            "wikitext": wikitext,
            "wikitext_hash": hashlib.sha1(wikitext.encode("utf-8")).hexdigest() if wikitext else None,
            "wikitext_length": len(wikitext),
        },
        "sentence_units": sentence_units,
        "observations": observations,
        "event_candidates": event_candidates,
        "timeline_projection": timeline_projection,
        "regime": regime,
        "parser": aoo_payload.get("parser"),
        "extraction_profile": aoo_payload.get("extraction_profile"),
        "summary": {
            "sentence_unit_count": len(sentence_units),
            "observation_count": len(observations),
            "event_candidate_count": len(event_candidates),
            "timeline_event_count": len(timeline_projection),
            "anchor_status_counts": dict(sorted(anchor_counter.items())),
            "regime": regime,
        },
    }


def _state_from_event_payload(
    payload: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    article = _article_identity(snapshot or {}, payload)
    events = payload.get("events")
    raw_events = [dict(event) for event in events if isinstance(event, Mapping)] if isinstance(events, list) else []
    sentence_units: list[dict[str, Any]] = []
    for index, event in enumerate(raw_events, start=1):
        event_id = _safe_str(event.get("event_id")) or f"event:{index:04d}"
        sentence_units.append(
            {
                "unit_id": event_id,
                "event_id": event_id,
                "order_index": index,
                "section": str(event.get("section") or ""),
                "text": str(event.get("text") or ""),
                "links": list(event.get("links") or []),
                "links_para": list(event.get("links_para") or []),
                "anchor": dict(event.get("anchor")) if isinstance(event.get("anchor"), Mapping) else None,
                "anchor_candidates": [dict(item) for item in event.get("anchor_candidates") or [] if isinstance(item, Mapping)],
                "anchor_status": _anchor_status_from_anchor(event.get("anchor") if isinstance(event.get("anchor"), Mapping) else None),
                "ordering_basis": "source_text_order",
                "lane": str(event.get("lane") or "event_payload"),
            }
        )
    event_candidates = _extract_event_candidates(payload, sentence_units=sentence_units)
    observations = build_observations_from_event_candidates(event_candidates)
    timeline_projection = build_timeline_projection(event_candidates)
    source_text = str(snapshot.get("wikitext") or "") if isinstance(snapshot, Mapping) else ""
    if not source_text:
        source_text = "\n".join(
            str(event.get("text") or "") for event in raw_events if str(event.get("text") or "").strip()
        )
    anchor_counter = Counter(str(row.get("anchor_status") or "none") for row in timeline_projection)
    regime = _derive_regime_vector(sentence_units=sentence_units, event_candidates=event_candidates)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_at": _utc_now_iso(),
        "article": article,
        "source_text": {
            "wikitext": source_text,
            "wikitext_hash": hashlib.sha1(source_text.encode("utf-8")).hexdigest() if source_text else None,
            "wikitext_length": len(source_text),
        },
        "sentence_units": sentence_units,
        "observations": observations,
        "event_candidates": event_candidates,
        "timeline_projection": timeline_projection,
        "regime": regime,
        "parser": payload.get("parser"),
        "extraction_profile": payload.get("extraction_profile"),
        "summary": {
            "sentence_unit_count": len(sentence_units),
            "observation_count": len(observations),
            "event_candidate_count": len(event_candidates),
            "timeline_event_count": len(timeline_projection),
            "anchor_status_counts": dict(sorted(anchor_counter.items())),
            "regime": regime,
        },
    }


def coerce_wiki_article_state(
    *,
    snapshot: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(payload, Mapping) and payload.get("schema_version") == STATE_SCHEMA_VERSION:
        return dict(payload)
    snapshot_obj = coalesce_snapshot(snapshot, payload)
    if isinstance(payload, Mapping) and isinstance(payload.get("events"), list):
        return _state_from_event_payload(payload, snapshot=snapshot_obj)
    if snapshot_obj and str(snapshot_obj.get("wikitext") or "").strip():
        return build_wiki_article_state(snapshot_obj)
    return _state_from_event_payload({}, snapshot=snapshot_obj)
