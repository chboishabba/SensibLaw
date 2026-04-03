from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from src.policy.parliamentary_follow_control import compute_parliamentary_weight
from src.policy.state_follow_control import compute_state_awareness_priority
from src.ontology.debate_follow_contract import build_sample_debate_records
from src.review_geometry.reviewer_packets import (
    build_reviewer_packet,
    summarize_reviewer_packets,
)


LEGAL_FOLLOW_GRAPH_VERSION = "au.legal_follow_graph.v1"
FOLLOW_CONTROL_PLANE_VERSION = "follow.control.v1"


def _build_follow_control_plane(
    *,
    source_family: str,
    hint_kind: str,
    receipt_kind: str,
    substrate_kind: str,
    conjecture_kind: str,
    route_targets: Sequence[str] | None = None,
    resolution_statuses: Sequence[str] | None = None,
    reference_levels: Sequence[str] | None = None,
) -> dict[str, Any]:
    priority = compute_state_awareness_priority(reference_levels or [])
    return {
        "version": FOLLOW_CONTROL_PLANE_VERSION,
        "source_family": str(source_family),
        "hint_kind": str(hint_kind),
        "receipt_kind": str(receipt_kind),
        "substrate_kind": str(substrate_kind),
        "conjecture_kind": str(conjecture_kind),
        "route_targets": sorted(
            {str(value) for value in route_targets or [] if str(value).strip()}
        ),
        "resolution_statuses": sorted(
            {str(value) for value in resolution_statuses or [] if str(value).strip()}
        ),
        "state_awareness_priority": priority,
    }


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())
    return cleaned.strip("_").lower() or "unknown"


def _event_label(event: Mapping[str, Any]) -> str:
    section = str(event.get("section") or event.get("event_section") or "").strip()
    if section:
        return section
    event_id = str(event.get("event_id") or "").strip()
    return event_id or "AU event"


def _normalize_legal_ref_value(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("legal_ref:"):
        raw = raw.split(":", 1)[1]
    return raw.replace("_", " ").strip()


def _classify_legal_ref(value: str) -> str:
    normalized = _normalize_legal_ref_value(value).casefold()
    raw = str(value or "").casefold()
    if not normalized:
        return "legal_ref"
    if any(token in normalized for token in (" act ", " statute ", " regulation ", " ordinance ", " bill ")):
        return "supporting_legislation"
    if any(token in normalized for token in ("instrument", "treaty", "agreement", "protocol", "convention", "charter")):
        return "cited_instrument"
    if "_act_" in raw or raw.endswith("_act") or "act " in normalized or normalized.endswith(" act"):
        return "supporting_legislation"
    if "_v_" in raw or " hca " in normalized or " fca " in normalized or " court " in normalized:
        return "case_ref"
    return "legal_ref"


def _detail_classification(details: Sequence[Mapping[str, Any]] | None, canonical_ref: str) -> str | None:
    for row in details or ():
        if not isinstance(row, Mapping):
            continue
        if str(row.get("canonical_ref") or "").strip() != canonical_ref:
            continue
        ref_class = str(row.get("reference_class") or "").strip()
        if ref_class == "case":
            return "case_ref"
        if ref_class == "supporting_legislation":
            return "supporting_legislation"
        if ref_class in {"supporting_instrument", "cited_instrument"}:
            return "cited_instrument"
        if ref_class:
            return ref_class
    return None


def _detail_for_canonical_ref(
    details: Sequence[Mapping[str, Any]] | None,
    canonical_ref: str,
) -> dict[str, Any]:
    for row in details or ():
        if not isinstance(row, Mapping):
            continue
        if str(row.get("canonical_ref") or "").strip() != canonical_ref:
            continue
        return {
            "canonical_ref": str(row.get("canonical_ref") or "").strip() or None,
            "reference_class": str(row.get("reference_class") or "").strip() or None,
            "ref_kind": str(row.get("ref_kind") or "").strip() or None,
            "source_title": str(row.get("source_title") or "").strip() or None,
            "neutral_citation": str(row.get("neutral_citation") or "").strip() or None,
            "jurisdiction_hint": str(row.get("jurisdiction_hint") or "").strip()
            or _infer_detail_jurisdiction_hint(row, canonical_ref),
            "instrument_kind": str(row.get("instrument_kind") or "").strip()
            or _infer_detail_instrument_kind(row, canonical_ref),
        }
    return {}


def _citation_detail_for_text(
    details: Sequence[Mapping[str, Any]] | None,
    citation_text: str,
) -> dict[str, Any]:
    for row in details or ():
        if not isinstance(row, Mapping):
            continue
        if str(row.get("raw_text") or "").strip() != citation_text:
            continue
        return {
            "raw_text": str(row.get("raw_text") or "").strip() or None,
            "neutral_citation": str(row.get("neutral_citation") or "").strip() or None,
            "court_hint": str(row.get("court_hint") or "").strip() or None,
            "year_hint": row.get("year_hint"),
        }
    return {}


def _infer_detail_jurisdiction_hint(detail: Mapping[str, Any], canonical_ref: str) -> str | None:
    raw = " ".join(
        str(value or "").strip()
        for value in (
            detail.get("source_title"),
            detail.get("canonical_ref"),
            canonical_ref,
        )
        if str(value or "").strip()
    ).casefold()
    if not raw:
        return None
    if any(token in raw for token in ("commonwealth", " australia ", " aust ", " cth ")):
        return "CTH"
    for token in ("NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT", "HCA"):
        if token.casefold() in raw:
            return token
    return None


def _infer_detail_instrument_kind(detail: Mapping[str, Any], canonical_ref: str) -> str | None:
    raw = " ".join(
        str(value or "").strip()
        for value in (
            detail.get("ref_kind"),
            detail.get("source_title"),
            detail.get("canonical_ref"),
            canonical_ref,
        )
        if str(value or "").strip()
    ).casefold()
    if not raw:
        return None
    for token, label in (
        (" act ", "act"),
        (" regulation ", "regulation"),
        (" rules ", "rule"),
        (" rule ", "rule"),
        (" ordinance ", "ordinance"),
        (" order ", "order"),
        (" treaty ", "treaty"),
        (" protocol ", "protocol"),
        (" convention ", "convention"),
        (" charter ", "charter"),
        (" instrument ", "instrument"),
    ):
        if token in f" {raw} ":
            return label
    return None


def _edge_kind_for_legal_ref(classification: str, prefix: str) -> str:
    if classification == "supporting_legislation":
        return f"{prefix}_supporting_legislation"
    if classification == "cited_instrument":
        return f"{prefix}_cited_instrument"
    if classification == "case_ref":
        return f"{prefix}_case_ref"
    return f"{prefix}_legal_ref"


_SUPPORTING_LEGISLATION_ROLE_HINTS: Sequence[tuple[Sequence[str], str]] = (
    (("support", "supporting", "statute", "enable", "empower", "authoris", "permit", "allow"), "enabling_legislation"),
    (("limit", "restrict", "prohibit", "ban", "forbid", "constrain", "regulate"), "constraining_legislation"),
    (("procedur", "procedure", "trial", "hearing", "appeal", "process"), "procedural_legislation"),
    (("delegate", "delegat", "instrument"), "delegated_instrument_parent"),
    (("amend", "amended", "amendment", "repeal", "revise"), "amending_legislation"),
)


def _supporting_legislation_roles_from_texts(texts: Sequence[str]) -> list[str]:
    combined = " ".join(str(text or "").lower() for text in texts if text).strip()
    roles: set[str] = set()
    if not combined:
        return []
    for keywords, role in _SUPPORTING_LEGISLATION_ROLE_HINTS:
        if any(keyword in combined for keyword in keywords):
            roles.add(role)
    return sorted(roles)


def _supporting_legislation_roles_from_context(
    event_map: Mapping[str, Mapping[str, Any]],
    event_ids: Sequence[str] | None,
    detail: Mapping[str, Any] | None,
) -> list[str]:
    texts: list[str] = []
    for event_id in event_ids or ():
        row = event_map.get(event_id)
        if isinstance(row, Mapping):
            event_text = str(row.get("event_text") or row.get("text") or "").strip()
            event_section = str(row.get("event_section") or row.get("section") or "").strip()
            texts.extend([event_text, event_section])
    if isinstance(detail, Mapping):
        for key in ("source_title", "canonical_ref", "ref_kind", "reference_class"):
            value = str(detail.get(key) or "").strip()
            if value:
                texts.append(value)
    return _supporting_legislation_roles_from_texts(texts)


_UK_HINT_PATTERNS = (
    re.compile(r"\buk\b"),
    re.compile(r"\bunited kingdom\b"),
    re.compile(r"\bgreat britain\b"),
    re.compile(r"\bbritish\b"),
    re.compile(r"\bbritain\b"),
    re.compile(r"\bengland\b"),
    re.compile(r"\bscotland\b"),
    re.compile(r"\bwales\b"),
    re.compile(r"northern ireland"),
    re.compile(r"\bukhl\b"),
    re.compile(r"\bukpc\b"),
    re.compile(r"\buksc\b"),
    re.compile(r"\bukhc\b"),
)
_UK_SUPPORTING_KINDS = {
    "authority_receipt",
    "legal_ref",
    "case_ref",
    "supporting_legislation",
    "cited_instrument",
    "citation",
}
_UK_HINT_FIELD_EXCLUSIONS = {"ingest_run_id"}


def _value_contains_uk_hint(value: str | None) -> bool:
    if not value:
        return False
    lower = value.lower()
    if ".uk" in lower:
        return True
    return any(pattern.search(lower) for pattern in _UK_HINT_PATTERNS)


def _uk_hint_fields_for_node(node: Mapping[str, Any]) -> set[str]:
    kind = str(node.get("kind") or "")
    if kind not in _UK_SUPPORTING_KINDS:
        return set()
    metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
    fields: set[str] = set()

    def _check(field_name: str, candidate: Any) -> None:
        if isinstance(candidate, str) and _value_contains_uk_hint(candidate):
            fields.add(field_name)

    _check("label", node.get("label"))
    for key, value in metadata.items():
        if key in _UK_HINT_FIELD_EXCLUSIONS:
            continue
        _check(key, value)
    return fields


def _is_blank_metadata(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, (list, tuple, set)) and len(value) == 0:
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


def _merge_metadata_value(existing: Any, incoming: Any) -> Any:
    if _is_blank_metadata(incoming):
        return existing
    if _is_blank_metadata(existing):
        return incoming
    if isinstance(existing, list) and isinstance(incoming, list):
        merged: list[Any] = []
        for value in list(existing) + list(incoming):
            if value not in merged:
                merged.append(value)
        return merged
    if isinstance(existing, dict) and isinstance(incoming, dict):
        merged = dict(existing)
        for key, value in incoming.items():
            merged[key] = _merge_metadata_value(merged.get(key), value)
        return merged
    return existing


def _metadata_label_counts(
    nodes: Sequence[Mapping[str, Any]],
    *,
    kinds: set[str],
    metadata_key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in nodes:
        if str(row.get("kind") or "") not in kinds:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        label = str(metadata.get(metadata_key) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _edge_metadata_label_counts(
    edges: Sequence[Mapping[str, Any]],
    *,
    metadata_key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in edges:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        label = str(metadata.get(metadata_key) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _kind_counts(rows: Sequence[Mapping[str, Any]], *, field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _list_metadata_counts(
    nodes: Sequence[Mapping[str, Any]],
    *,
    kinds: set[str],
    metadata_key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in nodes:
        if row.get("kind") not in kinds:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        values = metadata.get(metadata_key)
        if isinstance(values, list):
            for value in values:
                label = str(value or "").strip()
                if not label:
                    continue
                counts[label] = counts.get(label, 0) + 1
        elif values not in {None, ""}:
            label = str(values).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return counts


def _metadata_numeric_counts(
    nodes: Sequence[Mapping[str, Any]],
    *,
    kinds: set[str],
    metadata_key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in nodes:
        if str(row.get("kind") or "") not in kinds:
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        value = metadata.get(metadata_key)
        if value in {None, ""}:
            continue
        label = str(value)
        counts[label] = counts.get(label, 0) + 1
    return counts


def build_au_legal_follow_graph(
    semantic_report: Mapping[str, Any],
    *,
    source_events: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    authority_receipts = (
        semantic_report.get("authority_receipts")
        if isinstance(semantic_report.get("authority_receipts"), Mapping)
        else {}
    )
    items = authority_receipts.get("items") if isinstance(authority_receipts.get("items"), list) else []
    follow_needed_events = (
        authority_receipts.get("follow_needed_events")
        if isinstance(authority_receipts.get("follow_needed_events"), list)
        else []
    )

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    node_index: dict[str, dict[str, Any]] = {}

    event_map: dict[str, Mapping[str, Any]] = {}
    for row in source_events or ():
        if isinstance(row, Mapping):
            event_id = str(row.get("event_id") or "").strip()
            if event_id:
                event_map[event_id] = row
    for row in follow_needed_events:
        if isinstance(row, Mapping):
            event_id = str(row.get("event_id") or "").strip()
            if event_id and event_id not in event_map:
                event_map[event_id] = row
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for event_id in item.get("linked_event_ids", []):
            normalized = str(event_id or "").strip()
            if normalized and normalized not in event_map:
                event_map[normalized] = {"event_id": normalized}

    def add_node(node_id: str, *, kind: str, label: str, metadata: Mapping[str, Any] | None = None) -> None:
        clean_metadata = {key: value for key, value in dict(metadata or {}).items() if value is not None}
        if node_id in seen_nodes:
            existing = node_index[node_id]
            if not existing.get("label") and label:
                existing["label"] = label
            merged = dict(existing.get("metadata") or {})
            for key, value in clean_metadata.items():
                merged[key] = _merge_metadata_value(merged.get(key), value)
            existing["metadata"] = merged
            return
        seen_nodes.add(node_id)
        node = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "metadata": clean_metadata,
        }
        node_index[node_id] = node
        nodes.append(node)

    def add_edge(source: str, target: str, *, kind: str, metadata: Mapping[str, Any] | None = None) -> None:
        key = (source, target, kind)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": kind,
                "metadata": dict(metadata or {}),
            }
        )

    def _ensure_debate_target_node(target_id: str) -> None:
        if not target_id:
            return
        if target_id in node_index:
            return
        target_kind = "case_reference" if target_id.startswith("case:") else "legal_instrument"
        add_node(
            target_id,
            kind=target_kind,
            label=target_id,
            metadata={"advisory": "debate_target"},
        )

    def _inject_debate_records() -> None:
        debates = build_sample_debate_records()
        for record in debates.values():
            add_node(
                record.debate_id,
                kind="debate_record",
                label=f"{record.legislature} {record.chamber} debate",
                metadata={
                    "legislature": record.legislature,
                    "chamber": record.chamber,
                    "date": record.date,
                    "summary": record.summary,
                    "influence_tags": list(record.influence_tags),
                    "edges": list(record.edges),
                },
            )
            for edge_descriptor in record.edges:
                parts = edge_descriptor.split(":", 1)
                if len(parts) != 2:
                    continue
                relation, target = parts
                target_id = target.strip()
                if not target_id:
                    continue
                _ensure_debate_target_node(target_id)
                add_edge(
                    record.debate_id,
                    target_id,
                    kind=relation,
                    metadata={
                        "derived_from": record.debate_id,
                        "advisory": True,
                    },
                )

    for event_id, row in sorted(event_map.items()):
        add_node(
            f"event:{event_id}",
            kind="event",
            label=_event_label(row),
            metadata={
                "event_id": event_id,
                "event_section": str(row.get("section") or row.get("event_section") or "").strip() or None,
                "event_text": str(row.get("text") or row.get("event_text") or "").strip()[:240] or None,
            },
        )

    _inject_debate_records()

    for row in follow_needed_events:
        if not isinstance(row, Mapping):
            continue
        event_id = str(row.get("event_id") or "").strip()
        if not event_id:
            continue
        event_node_id = f"event:{event_id}"
        for title in row.get("authority_titles", []):
            normalized = str(title or "").strip()
            if not normalized:
                continue
            authority_node_id = f"authority_title:{_slug(normalized)}"
            add_node(
                authority_node_id,
                kind="authority_title",
                label=normalized,
                metadata={
                    "supporting_event_ids": [event_id],
                    "supporting_event_sections": [str(row.get("event_section") or "").strip()] if str(row.get("event_section") or "").strip() else [],
                },
            )
            add_edge(event_node_id, authority_node_id, kind="mentions_authority_title")
        for ref in row.get("legal_refs", []):
            normalized = str(ref or "").strip()
            if not normalized:
                continue
            detail = _detail_for_canonical_ref(row.get("legal_ref_details"), normalized)
            classification = str(detail.get("reference_class") or "").strip()
            if classification == "case":
                classification = "case_ref"
            elif classification == "supporting_instrument":
                classification = "cited_instrument"
            classification = classification or _classify_legal_ref(normalized)
            ref_node_id = f"{classification}:{_slug(normalized)}"
            metadata = {
                "canonical_ref": normalized,
                "reference_kind": classification,
                "reference_class": detail.get("reference_class"),
                "ref_kind": detail.get("ref_kind"),
                "source_title": detail.get("source_title"),
                "neutral_citation": detail.get("neutral_citation"),
                "jurisdiction_hint": detail.get("jurisdiction_hint"),
                "instrument_kind": detail.get("instrument_kind"),
                "supporting_event_ids": [event_id],
                "supporting_event_sections": [str(row.get("event_section") or "").strip()] if str(row.get("event_section") or "").strip() else [],
            }
            if classification == "supporting_legislation":
                roles = _supporting_legislation_roles_from_context(event_map, [event_id], detail)
                if roles:
                    metadata["supporting_legislation_roles"] = roles
            add_node(
                ref_node_id,
                kind=classification,
                label=_normalize_legal_ref_value(normalized),
                metadata=metadata,
            )
            add_edge(
                event_node_id,
                ref_node_id,
                kind=_edge_kind_for_legal_ref(classification, "mentions"),
                metadata={
                    "reference_kind": classification,
                    "reference_class": detail.get("reference_class"),
                    "ref_kind": detail.get("ref_kind"),
                    "canonical_ref": normalized,
                    "jurisdiction_hint": detail.get("jurisdiction_hint"),
                    "instrument_kind": detail.get("instrument_kind"),
                    "supporting_event_id": event_id,
                },
            )
        for citation in row.get("candidate_citations", []):
            normalized = str(citation or "").strip()
            if not normalized:
                continue
            citation_detail = _citation_detail_for_text(row.get("candidate_citation_details"), normalized)
            citation_node_id = f"citation:{_slug(normalized)}"
            add_node(
                citation_node_id,
                kind="citation",
                label=normalized,
                metadata={
                    **citation_detail,
                    "supporting_event_ids": [event_id],
                    "supporting_event_sections": [str(row.get("event_section") or "").strip()] if str(row.get("event_section") or "").strip() else [],
                },
            )
            add_edge(
                event_node_id,
                citation_node_id,
                kind="mentions_citation",
                metadata={key: value for key, value in citation_detail.items() if key != "raw_text"},
            )

    for item in items:
        if not isinstance(item, Mapping):
            continue
        ingest_run_id = str(item.get("ingest_run_id") or "").strip()
        if not ingest_run_id:
            continue
        structured_summary = item.get("structured_summary") if isinstance(item.get("structured_summary"), Mapping) else {}
        receipt_node_id = f"authority_receipt:{_slug(ingest_run_id)}"
        citation = str(item.get("citation") or "").strip()
        add_node(
            receipt_node_id,
            kind="authority_receipt",
            label=citation or ingest_run_id,
            metadata={
                "ingest_run_id": ingest_run_id,
                "authority_kind": str(item.get("authority_kind") or "").strip() or None,
                "ingest_mode": str(item.get("ingest_mode") or "").strip() or None,
                "resolved_url": str(item.get("resolved_url") or "").strip() or None,
                "link_status": str(item.get("link_status") or "").strip() or None,
                "selected_paragraph_numbers": list(structured_summary.get("selected_paragraph_numbers") or []),
                "linked_event_sections": list(structured_summary.get("linked_event_sections") or []),
                "detected_neutral_citations": list(structured_summary.get("detected_neutral_citations") or []),
                "linked_event_ids": list(item.get("linked_event_ids") or []),
            },
        )
        for event_id in item.get("linked_event_ids", []):
            normalized = str(event_id or "").strip()
            if normalized:
                add_edge(
                    f"event:{normalized}",
                    receipt_node_id,
                    kind="linked_authority_receipt",
                    metadata={
                        "authority_kind": str(item.get("authority_kind") or "").strip() or None,
                        "ingest_run_id": ingest_run_id,
                    },
                )
                add_edge(
                    f"event:{normalized}",
                    receipt_node_id,
                    kind="supported_by_authority_receipt",
                    metadata={
                        "authority_kind": str(item.get("authority_kind") or "").strip() or None,
                        "ingest_run_id": ingest_run_id,
                        "selected_paragraph_numbers": list(structured_summary.get("selected_paragraph_numbers") or []),
                    },
                )
        if citation:
            citation_detail = _citation_detail_for_text(
                structured_summary.get("detected_neutral_citation_details"),
                citation,
            )
            citation_node_id = f"citation:{_slug(citation)}"
            add_node(
                citation_node_id,
                kind="citation",
                label=citation,
                metadata={
                    **citation_detail,
                    "supporting_receipt_ids": [ingest_run_id],
                    "supporting_authority_kinds": [str(item.get("authority_kind") or "").strip()] if str(item.get("authority_kind") or "").strip() else [],
                },
            )
            add_edge(
                receipt_node_id,
                citation_node_id,
                kind="resolved_citation",
                metadata={
                    key: value
                    for key, value in {
                        **citation_detail,
                        "ingest_run_id": ingest_run_id,
                        "authority_kind": str(item.get("authority_kind") or "").strip() or None,
                        "supporting_receipt_ids": [ingest_run_id],
                    }.items()
                    if key != "raw_text"
                },
            )
        for title in item.get("matched_authority_titles", []):
            normalized = str(title or "").strip()
            if not normalized:
                continue
            authority_node_id = f"authority_title:{_slug(normalized)}"
            add_node(
                authority_node_id,
                kind="authority_title",
                label=normalized,
                metadata={
                    "supporting_receipt_ids": [ingest_run_id],
                    "supporting_authority_kinds": [str(item.get("authority_kind") or "").strip()] if str(item.get("authority_kind") or "").strip() else [],
                },
            )
            add_edge(receipt_node_id, authority_node_id, kind="supports_authority_title")
        for ref in item.get("matched_legal_refs", []):
            normalized = str(ref or "").strip()
            if not normalized:
                continue
            detail = _detail_for_canonical_ref(item.get("matched_legal_ref_details"), normalized)
            classification = str(detail.get("reference_class") or "").strip()
            if classification == "case":
                classification = "case_ref"
            elif classification == "supporting_instrument":
                classification = "cited_instrument"
            classification = classification or _classify_legal_ref(normalized)
            ref_node_id = f"{classification}:{_slug(normalized)}"
            metadata = {
                "canonical_ref": normalized,
                "reference_kind": classification,
                "reference_class": detail.get("reference_class"),
                "ref_kind": detail.get("ref_kind"),
                "source_title": detail.get("source_title"),
                "neutral_citation": detail.get("neutral_citation"),
                "jurisdiction_hint": detail.get("jurisdiction_hint"),
                "instrument_kind": detail.get("instrument_kind"),
                "supporting_receipt_ids": [ingest_run_id],
                "supporting_authority_kinds": [str(item.get("authority_kind") or "").strip()] if str(item.get("authority_kind") or "").strip() else [],
            }
            if classification == "supporting_legislation":
                roles = _supporting_legislation_roles_from_context(
                    event_map,
                    list(item.get("linked_event_ids", [])),
                    detail,
                )
                if roles:
                    metadata["supporting_legislation_roles"] = roles
            add_node(
                ref_node_id,
                kind=classification,
                label=_normalize_legal_ref_value(normalized),
                metadata=metadata,
            )
            add_edge(
                receipt_node_id,
                ref_node_id,
                kind=_edge_kind_for_legal_ref(classification, "supports"),
                metadata={
                    "reference_kind": classification,
                    "reference_class": detail.get("reference_class"),
                    "ref_kind": detail.get("ref_kind"),
                    "canonical_ref": normalized,
                    "jurisdiction_hint": detail.get("jurisdiction_hint"),
                    "instrument_kind": detail.get("instrument_kind"),
                },
            )

    uk_supporting_nodes: dict[str, set[str]] = {}
    for node in nodes:
        fields = _uk_hint_fields_for_node(node)
        if fields:
            uk_supporting_nodes[node["id"]] = fields
    if uk_supporting_nodes:
        derived_node_id = "derived_follow_target:uk_british"
        add_node(
            derived_node_id,
            kind="derived_follow_target",
            label="UK/British legal follow target",
            metadata={
                "supporting_node_ids": sorted(uk_supporting_nodes),
                "supporting_fields": sorted(
                    {field for fields in uk_supporting_nodes.values() for field in fields}
                ),
            },
        )
        for source_id, fields in sorted(uk_supporting_nodes.items()):
            add_edge(
                source_id,
                derived_node_id,
                kind="suggests_uk_follow_target",
                metadata={"derived_reason_fields": sorted(fields)},
            )

    supporting_receipt_ids = [receipt_id for row in nodes for receipt_id in row["metadata"].get("supporting_receipt_ids", [])]
    supporting_authority_kinds: dict[str, int] = {}
    for row in nodes:
        for kind in row["metadata"].get("supporting_authority_kinds", []):
            supporting_authority_kinds[kind] = supporting_authority_kinds.get(kind, 0) + 1
    return {
        "version": LEGAL_FOLLOW_GRAPH_VERSION,
        "derived_only": True,
        "challengeable": True,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "event_count": sum(1 for row in nodes if row["kind"] == "event"),
            "authority_title_count": sum(1 for row in nodes if row["kind"] == "authority_title"),
            "legal_ref_count": sum(
                1
                for row in nodes
                if row["kind"] in {"legal_ref", "case_ref", "supporting_legislation", "cited_instrument"}
            ),
            "case_ref_count": sum(1 for row in nodes if row["kind"] == "case_ref"),
            "supporting_legislation_count": sum(1 for row in nodes if row["kind"] == "supporting_legislation"),
            "cited_instrument_count": sum(1 for row in nodes if row["kind"] == "cited_instrument"),
            "citation_count": sum(1 for row in nodes if row["kind"] == "citation"),
            "authority_receipt_count": sum(1 for row in nodes if row["kind"] == "authority_receipt"),
            "derived_follow_target_count": sum(1 for row in nodes if row["kind"] == "derived_follow_target"),
            "derived_uk_follow_target_supporting_node_count": len(uk_supporting_nodes),
            "supporting_receipt_count": len(set(supporting_receipt_ids)),
            "supporting_authority_kind_counts": supporting_authority_kinds,
            "reference_kind_counts": _metadata_label_counts(
                nodes,
                kinds={"legal_ref", "case_ref", "supporting_legislation", "cited_instrument"},
                metadata_key="reference_kind",
            ),
            "reference_class_counts": _metadata_label_counts(
                nodes,
                kinds={"legal_ref", "case_ref", "supporting_legislation", "cited_instrument"},
                metadata_key="reference_class",
            ),
            "ref_kind_counts": _metadata_label_counts(
                nodes,
                kinds={"legal_ref", "case_ref", "supporting_legislation", "cited_instrument"},
                metadata_key="ref_kind",
            ),
            "jurisdiction_hint_counts": _metadata_label_counts(
                nodes,
                kinds={"legal_ref", "case_ref", "supporting_legislation", "cited_instrument"},
                metadata_key="jurisdiction_hint",
            ),
            "instrument_kind_counts": _metadata_label_counts(
                nodes,
                kinds={"supporting_legislation", "cited_instrument"},
                metadata_key="instrument_kind",
            ),
            "supporting_legislation_role_counts": _list_metadata_counts(
                nodes,
                kinds={"supporting_legislation"},
                metadata_key="supporting_legislation_roles",
            ),
            "citation_court_hint_counts": _metadata_label_counts(
                nodes,
                kinds={"citation"},
                metadata_key="court_hint",
            ),
            "citation_year_counts": _metadata_numeric_counts(
                nodes,
                kinds={"citation"},
                metadata_key="year_hint",
            ),
            "edge_kind_counts": _kind_counts(edges, field="kind"),
            "edge_reference_class_counts": _edge_metadata_label_counts(edges, metadata_key="reference_class"),
            "edge_ref_kind_counts": _edge_metadata_label_counts(edges, metadata_key="ref_kind"),
        },
    }


def build_au_legal_follow_operator_view(graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    summary = dict(graph.get("summary", {})) if isinstance(graph.get("summary"), Mapping) else {}
    node_map = {str(row.get("id") or ""): row for row in nodes if str(row.get("id") or "").strip()}

    supporting_edges: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        if str(edge.get("kind") or "") != "suggests_uk_follow_target":
            continue
        target = str(edge.get("target") or "").strip()
        source = str(edge.get("source") or "").strip()
        if not target or not source:
            continue
        supporting_edges.setdefault(target, []).append(
            {
                "source_id": source,
                "source_label": str((node_map.get(source) or {}).get("label") or source),
                "source_kind": str((node_map.get(source) or {}).get("kind") or ""),
                "derived_reason_fields": list(
                    (edge.get("metadata") or {}).get("derived_reason_fields", [])
                )
                if isinstance(edge.get("metadata"), Mapping)
                else [],
            }
        )

    edges_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        source_id = str(edge.get("source") or "").strip()
        if source_id:
            edges_by_source.setdefault(source_id, []).append(edge)

    queue: list[dict[str, Any]] = []
    for node in nodes:
        if str(node.get("kind") or "") != "derived_follow_target":
            continue
        node_id = str(node.get("id") or "").strip()
        metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
        supporting = supporting_edges.get(node_id, [])
        label = str(node.get("label") or "").strip() or "AU legal follow target"
        route_target = "uk_british_legal_follow"
        queue.append(
            build_reviewer_packet(
                item_id=node_id,
                title=label,
                subtitle="follow_needed_conjecture",
                description="Derived AU legal-follow target requiring bounded cross-jurisdiction review.",
                conjecture_kind="follow_needed_conjecture",
                route_target=route_target,
                resolution_status="open",
                chips=["cross_jurisdiction", "derived_follow_target"],
                detail_rows=[
                    {
                        "label": "Supporting nodes",
                        "value": ", ".join(row["source_label"] for row in supporting) or "none",
                    },
                    {
                        "label": "Supporting fields",
                        "value": ", ".join(str(value) for value in metadata.get("supporting_fields", [])) or "none",
                    },
                ],
                extra={
                    "supporting_node_ids": list(metadata.get("supporting_node_ids", [])),
                    "supporting_fields": list(metadata.get("supporting_fields", [])),
                    "supporting_nodes": supporting,
                },
            )
        )

    for node in nodes:
        if str(node.get("kind") or "") != "debate_record":
            continue
        node_id = str(node.get("id") or "").strip()
        metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
        debate_edges = edges_by_source.get(node_id, [])
        influence_tags = [str(item) for item in metadata.get("influence_tags", []) if item]
        edge_descriptions: list[str] = []
        for edge in debate_edges:
            edge_metadata = edge.get("metadata") if isinstance(edge.get("metadata"), Mapping) else {}
            parts: list[str] = [edge["kind"], edge.get("target", "")]
            instrument_type = str(edge_metadata.get("instrument_type") or "").strip()
            if instrument_type:
                parts.append(f"[{instrument_type}]")
            edge_note = str(edge_metadata.get("edge_note") or "").strip()
            if edge_note:
                parts.append(f"({edge_note})")
            edge_descriptions.append(" ".join(str(part) for part in parts if part))
        queue.append(
            build_reviewer_packet(
                item_id=node_id or "debate_record",
                title=str(node.get("label") or "Parliamentary debate"),
                subtitle="debate_follow_advisory",
                description="Advisory debate noting references to treaties/statutes/cases; remains non-binding.",
                conjecture_kind="debate_follow_advisory",
                route_target="debate_review",
                resolution_status="open",
                chips=["debate", "non_binding"],
                detail_rows=[
                    {"label": "Influence tags", "value": ", ".join(influence_tags) or "none"},
                    {"label": "Edge highlights", "value": "; ".join(edge_descriptions) or "none"},
                    {"label": "Summary", "value": metadata.get("summary") or "none"},
                ],
                extra={
                    "legislature": metadata.get("legislature"),
                    "chamber": metadata.get("chamber"),
                    "debate_edges": edge_descriptions,
                },
            )
        )

    queue_summary = summarize_reviewer_packets(queue)
    return {
        "available": bool(nodes),
        "control_plane": _build_follow_control_plane(
            source_family="au_legal_follow",
            hint_kind="legal_follow_hint",
            receipt_kind="authority_receipt",
            substrate_kind="legal_follow_graph",
            conjecture_kind="follow_needed_conjecture",
            route_targets=list(queue_summary["route_target_counts"].keys()) or [
                "uk_british_legal_follow",
                "manual_review",
            ],
            resolution_statuses=list(queue_summary["resolution_status_counts"].keys()) or [
                "open",
                "resolved",
                "reviewed",
            ],
            reference_levels=["eu", "member_state"],
        ),
        "summary": {
            **summary,
            "route_target_counts": queue_summary["route_target_counts"],
            "resolution_status_counts": queue_summary["resolution_status_counts"],
            "queue_count": queue_summary["queue_count"],
        },
        "queue": queue,
        "parliamentary_follow_control": compute_parliamentary_weight([
            "debate",
            "committee_report",
        ]),
        "parliamentary_samples": [
            asdict(record)
            for record in list(build_sample_debate_records().values())[:2]
        ],
    }


__all__ = [
    "LEGAL_FOLLOW_GRAPH_VERSION",
    "build_au_legal_follow_graph",
    "build_au_legal_follow_operator_view",
]
