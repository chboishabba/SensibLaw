from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence


CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION = "sl.cross_source_event_braid.v0_1"

_TEXT_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "to",
    "was",
    "were",
    "with",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _tokenize(text: str) -> set[str]:
    cleaned = []
    for token in _text(text).lower().replace("/", " ").replace("-", " ").split():
        token = "".join(ch for ch in token if ch.isalnum())
        if len(token) < 3 or token in _TEXT_STOPWORDS:
            continue
        cleaned.append(token)
    return set(cleaned)


def _canonical_key(entity: Mapping[str, Any] | None) -> str:
    entity = entity if isinstance(entity, Mapping) else {}
    return _text(entity.get("canonical_key"))


def _entity_kind(entity: Mapping[str, Any] | None) -> str:
    entity = entity if isinstance(entity, Mapping) else {}
    return _text(entity.get("entity_kind"))


def _citation_signature(citation: Mapping[str, Any]) -> str:
    return "|".join(
        (
            _text(citation.get("kind")),
            _text(citation.get("text")),
            _text(citation.get("source_id")),
        )
    )


def _event_key(row: Mapping[str, Any]) -> str:
    source_family = _text(row.get("source_family"))
    event_id = _text(row.get("event_id"))
    return f"{source_family}:{event_id}" if source_family and event_id else ""


def _doc_locator(row: Mapping[str, Any]) -> str:
    for field in ("source_path", "source_url", "doc_title", "source_id"):
        value = _text(row.get(field))
        if value:
            return value
    return _event_key(row)


def _role_signatures(row: Mapping[str, Any]) -> set[str]:
    signatures: set[str] = set()
    for role in _clean_mapping_rows(row.get("event_roles")):
        role_kind = _text(role.get("role_kind"))
        entity_key = _canonical_key(role.get("entity"))
        if role_kind and entity_key:
            signatures.add(f"{role_kind}:{entity_key}")
    return signatures


def _participant_keys(row: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for role in _clean_mapping_rows(row.get("event_roles")):
        entity_key = _canonical_key(role.get("entity"))
        if entity_key:
            keys.add(entity_key)
    for relation_field in ("relation_candidates", "promoted_relations", "candidate_only_relations"):
        for relation in _clean_mapping_rows(row.get(relation_field)):
            for side in ("subject", "object"):
                entity_key = _canonical_key(relation.get(side))
                if entity_key:
                    keys.add(entity_key)
    return keys


def _legal_ref_keys(row: Mapping[str, Any]) -> set[str]:
    keys = {
        key
        for key in _participant_keys(row)
        if key.startswith("legal_ref:")
    }
    for mention in _clean_mapping_rows(row.get("mentions")):
        resolved_key = _canonical_key(mention.get("resolved_entity"))
        if resolved_key.startswith("legal_ref:"):
            keys.add(resolved_key)
    return keys


def _predicate_keys(row: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    for relation_field in ("relation_candidates", "promoted_relations", "candidate_only_relations"):
        for relation in _clean_mapping_rows(row.get(relation_field)):
            predicate_key = _text(relation.get("predicate_key"))
            if predicate_key:
                keys.add(predicate_key)
    return keys


def _citation_keys(row: Mapping[str, Any]) -> set[str]:
    return {
        _citation_signature(citation)
        for citation in _clean_mapping_rows(row.get("citation_refs"))
        if _citation_signature(citation)
    }


def _normalize_source_event_rows(source_family_runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in source_family_runs:
        source_family = _text(run.get("source_family"))
        direct_rows = _clean_mapping_rows(run.get("source_event_rows"))
        if direct_rows:
            for row in direct_rows:
                normalized = dict(row)
                normalized.setdefault("source_family", source_family)
                normalized.setdefault("source_event_key", _event_key(normalized))
                rows.append(normalized)
            continue

        timeline_payload = run.get("timeline_payload") if isinstance(run.get("timeline_payload"), Mapping) else {}
        semantic_report = run.get("semantic_report") if isinstance(run.get("semantic_report"), Mapping) else {}
        timeline_events = _clean_mapping_rows(timeline_payload.get("events"))
        semantic_per_event = {
            _text(item.get("event_id")): item
            for item in _clean_mapping_rows(semantic_report.get("per_event"))
            if _text(item.get("event_id"))
        }
        doc_counters: Counter[str] = Counter()
        for event in timeline_events:
            event_id = _text(event.get("event_id"))
            if not event_id:
                continue
            per_event = semantic_per_event.get(event_id, {})
            source_path = _text(event.get("path"))
            source_url = _text(event.get("url"))
            doc_title = _text(event.get("title"))
            doc_locator = source_path or source_url or doc_title or _text(event.get("source_id")) or event_id
            doc_counters[doc_locator] += 1
            citation_refs = [
                {
                    "kind": _text(citation.get("kind")),
                    "text": _text(citation.get("text") or citation.get("value")),
                    "source_id": _text(citation.get("source_id") or event.get("source_id")),
                    "follow": list(citation.get("follow", [])) if isinstance(citation.get("follow"), list) else [],
                }
                for citation in _clean_mapping_rows(event.get("citations"))
            ]
            row = {
                "source_family": source_family,
                "doc_id": f"{source_family}:{doc_locator}",
                "doc_title": doc_title or _text(event.get("section")) or doc_locator,
                "event_id": event_id,
                "source_event_key": f"{source_family}:{event_id}",
                "local_order_index": doc_counters[doc_locator] - 1,
                "anchor": dict(event.get("anchor") or {}),
                "text": _text(event.get("text")),
                "source_path": source_path,
                "source_url": source_url,
                "source_id": _text(event.get("source_id")),
                "citation_refs": citation_refs,
                "event_roles": _clean_mapping_rows(per_event.get("event_roles")),
                "relation_candidates": _clean_mapping_rows(per_event.get("relation_candidates")),
                "promoted_relations": _clean_mapping_rows(per_event.get("promoted_relations")),
                "candidate_only_relations": _clean_mapping_rows(per_event.get("candidate_only_relations")),
                "abstained_relation_candidates": _clean_mapping_rows(per_event.get("abstained_relation_candidates")),
                "mentions": _clean_mapping_rows(per_event.get("mentions")),
            }
            rows.append(row)
    return rows


def _build_link(
    *,
    link_id: str,
    link_type: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    support_basis: Sequence[str],
    support_event_ids: Sequence[str],
    promotion_status: str,
    confidence_band: str,
    features: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "link_id": link_id,
        "link_type": link_type,
        "left_source_event_id": _event_key(left),
        "right_source_event_id": _event_key(right),
        "source_event_ids": [_event_key(left), _event_key(right)],
        "support_basis": [_text(value) for value in support_basis if _text(value)],
        "support_event_ids": [_text(value) for value in support_event_ids if _text(value)],
        "promotion_status": promotion_status,
        "confidence_band": confidence_band,
        "source_families": sorted({_text(left.get("source_family")), _text(right.get("source_family"))} - {""}),
        "features": dict(features or {}),
    }


def _build_cross_document_candidates(source_event_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    next_id = 1
    rows = list(source_event_rows)
    for index, left in enumerate(rows):
        left_key = _event_key(left)
        if not left_key:
            continue
        left_doc = _doc_locator(left)
        left_tokens = _tokenize(_text(left.get("text")))
        left_predicates = _predicate_keys(left)
        left_participants = _participant_keys(left)
        left_legal_refs = _legal_ref_keys(left)
        left_citations = _citation_keys(left)
        left_roles = _role_signatures(left)
        for right in rows[index + 1 :]:
            right_key = _event_key(right)
            if not right_key or _doc_locator(right) == left_doc:
                continue
            right_tokens = _tokenize(_text(right.get("text")))
            shared_predicates = sorted(left_predicates & _predicate_keys(right))
            shared_participants = sorted(left_participants & _participant_keys(right))
            shared_legal_refs = sorted(left_legal_refs & _legal_ref_keys(right))
            shared_citations = sorted(left_citations & _citation_keys(right))
            shared_roles = sorted(left_roles & _role_signatures(right))
            raw_text_overlap = sorted(left_tokens & right_tokens)
            min_token_count = min(len(left_tokens), len(right_tokens)) or 1
            text_overlap_ratio = len(raw_text_overlap) / min_token_count
            bounded_text_overlap = raw_text_overlap if len(raw_text_overlap) >= 4 and text_overlap_ratio >= 0.35 else []

            bases: list[str] = []
            if shared_predicates:
                bases.append("predicate_family_overlap")
            if shared_participants:
                bases.append("participant_overlap")
            if shared_legal_refs:
                bases.append("legal_ref_overlap")
            if shared_citations:
                bases.append("citation_overlap")
            if shared_roles:
                bases.append("event_role_overlap")
            if bounded_text_overlap:
                bases.append("bounded_text_overlap")
            if not bases:
                continue

            features = {
                "shared_predicates": shared_predicates,
                "shared_participants": shared_participants,
                "shared_legal_refs": shared_legal_refs,
                "shared_citations": shared_citations,
                "shared_roles": shared_roles,
                "text_overlap_tokens": bounded_text_overlap[:8],
            }
            if (
                shared_predicates
                and ((shared_participants and shared_legal_refs) or len(shared_participants) >= 2 or (shared_participants and shared_citations))
            ):
                link_type = "same_event_as"
                promotion_status = "promoted"
                confidence_band = "high"
            elif shared_predicates and (shared_participants or shared_legal_refs):
                link_type = "overlaps_event"
                promotion_status = "candidate"
                confidence_band = "medium"
            elif shared_legal_refs:
                link_type = "same_legal_matter_as"
                promotion_status = "candidate"
                confidence_band = "medium"
            elif shared_roles or len(shared_participants) >= 2:
                link_type = "same_actor_role_as"
                promotion_status = "candidate"
                confidence_band = "low"
            elif shared_predicates or (shared_legal_refs and bounded_text_overlap):
                link_type = "refines"
                promotion_status = "candidate"
                confidence_band = "low"
            elif bounded_text_overlap:
                link_type = "overlaps_event"
                promotion_status = "candidate"
                confidence_band = "low"
            else:
                continue

            candidates.append(
                _build_link(
                    link_id=f"candidate_link:{next_id:04d}",
                    link_type=link_type,
                    left=left,
                    right=right,
                    support_basis=bases,
                    support_event_ids=[left_key, right_key],
                    promotion_status=promotion_status,
                    confidence_band=confidence_band,
                    features=features,
                )
            )
            next_id += 1
    return candidates


def _cluster_promoted_links(source_event_rows: Sequence[Mapping[str, Any]], promoted_links: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    parent = {_event_key(row): _event_key(row) for row in source_event_rows if _event_key(row)}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for link in promoted_links:
        left = _text(link.get("left_source_event_id"))
        right = _text(link.get("right_source_event_id"))
        if left in parent and right in parent:
            union(left, right)

    clusters: dict[str, list[str]] = defaultdict(list)
    for node in parent:
        clusters[find(node)].append(node)

    row_index = {_event_key(row): dict(row) for row in source_event_rows if _event_key(row)}
    merged_events: list[dict[str, Any]] = []
    event_to_merged_id: dict[str, str] = {}
    next_id = 1
    for members in sorted(clusters.values(), key=lambda values: (len(values), values), reverse=True):
        if len(members) < 2:
            continue
        merged_event_id = f"merged_event:{next_id:04d}"
        next_id += 1
        support_links = [
            link
            for link in promoted_links
            if _text(link.get("left_source_event_id")) in members and _text(link.get("right_source_event_id")) in members
        ]
        support_basis = sorted(
            {
                basis
                for link in support_links
                for basis in link.get("support_basis", [])
                if isinstance(basis, str) and basis.strip()
            }
        )
        promoted_predicates = sorted(
            {
                predicate
                for member in members
                for predicate in _predicate_keys(row_index.get(member, {}))
                if predicate
            }
        )
        for member in members:
            event_to_merged_id[member] = merged_event_id
        merged_events.append(
            {
                "merged_event_id": merged_event_id,
                "source_event_ids": members,
                "source_families": sorted({_text(row_index[member].get("source_family")) for member in members if member in row_index}),
                "support_basis": support_basis,
                "support_event_ids": sorted({event_id for link in support_links for event_id in link.get("support_event_ids", [])}),
                "promotion_status": "promoted",
                "confidence_band": "high",
                "promoted_predicates": promoted_predicates,
            }
        )
    return event_to_merged_id, merged_events


def _build_ordering_edges(source_event_rows: Sequence[Mapping[str, Any]], merged_event_lookup: Mapping[str, str]) -> list[dict[str, Any]]:
    by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    row_index = {_event_key(row): dict(row) for row in source_event_rows if _event_key(row)}
    for row in source_event_rows:
        doc_id = _text(row.get("doc_id")) or _doc_locator(row)
        if doc_id:
            by_doc[doc_id].append(dict(row))

    edges: list[dict[str, Any]] = []
    next_id = 1
    local_successors: dict[str, list[str]] = defaultdict(list)
    local_predecessors: dict[str, list[str]] = defaultdict(list)
    for doc_rows in by_doc.values():
        ordered = sorted(doc_rows, key=lambda row: int(row.get("local_order_index", 0) or 0))
        for left, right in zip(ordered, ordered[1:]):
            left_key = _event_key(left)
            right_key = _event_key(right)
            if not left_key or not right_key:
                continue
            local_successors[left_key].append(right_key)
            local_predecessors[right_key].append(left_key)
            edges.append(
                {
                    "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                    "source_event_id": left_key,
                    "target_event_id": right_key,
                    "source_event_ids": [left_key, right_key],
                    "source_families": sorted({_text(left.get("source_family")), _text(right.get("source_family"))} - {""}),
                    "support_basis": ["local_document_order"],
                    "support_event_ids": [left_key, right_key],
                    "promotion_status": "promoted",
                    "confidence_band": "high",
                    "source_merged_event_id": _text(merged_event_lookup.get(left_key)),
                    "target_merged_event_id": _text(merged_event_lookup.get(right_key)),
                }
            )
            next_id += 1

    merged_members: dict[str, list[str]] = defaultdict(list)
    for event_key, merged_event_id in merged_event_lookup.items():
        if merged_event_id:
            merged_members[merged_event_id].append(event_key)

    seen_cross_doc: set[tuple[str, str]] = set()
    for merged_event_id, members in merged_members.items():
        for member in members:
            for sibling in members:
                if member == sibling:
                    continue
                if _doc_locator(row_index.get(member, {})) == _doc_locator(row_index.get(sibling, {})):
                    continue
                for successor in local_successors.get(sibling, []):
                    if successor == member:
                        continue
                    key = (member, successor)
                    if key in seen_cross_doc:
                        continue
                    seen_cross_doc.add(key)
                    edges.append(
                        {
                            "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                            "source_event_id": member,
                            "target_event_id": successor,
                            "source_event_ids": [member, sibling, successor],
                            "source_families": sorted(
                                {
                                    _text(row_index.get(member, {}).get("source_family")),
                                    _text(row_index.get(sibling, {}).get("source_family")),
                                    _text(row_index.get(successor, {}).get("source_family")),
                                }
                                - {""}
                            ),
                            "support_basis": ["inferred_from_source_backed_overlap"],
                            "support_event_ids": [member, sibling, successor],
                            "promotion_status": "promoted",
                            "confidence_band": "medium",
                            "source_merged_event_id": merged_event_id,
                            "target_merged_event_id": _text(merged_event_lookup.get(successor)),
                        }
                    )
                    next_id += 1
                for predecessor in local_predecessors.get(member, []):
                    if predecessor == sibling:
                        continue
                    key = (predecessor, sibling)
                    if key in seen_cross_doc:
                        continue
                    seen_cross_doc.add(key)
                    edges.append(
                        {
                            "ordering_edge_id": f"ordering_edge:{next_id:04d}",
                            "source_event_id": predecessor,
                            "target_event_id": sibling,
                            "source_event_ids": [predecessor, member, sibling],
                            "source_families": sorted(
                                {
                                    _text(row_index.get(predecessor, {}).get("source_family")),
                                    _text(row_index.get(member, {}).get("source_family")),
                                    _text(row_index.get(sibling, {}).get("source_family")),
                                }
                                - {""}
                            ),
                            "support_basis": ["inferred_from_source_backed_overlap"],
                            "support_event_ids": [predecessor, member, sibling],
                            "promotion_status": "promoted",
                            "confidence_band": "medium",
                            "source_merged_event_id": _text(merged_event_lookup.get(predecessor)),
                            "target_merged_event_id": merged_event_id,
                        }
                    )
                    next_id += 1
    return edges


def summarize_cross_source_event_braid(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidate_links = _clean_mapping_rows(payload.get("candidate_links"))
    merged_events = _clean_mapping_rows(payload.get("merged_events"))
    ordering_edges = _clean_mapping_rows(payload.get("ordering_edges"))
    source_event_rows = _clean_mapping_rows(payload.get("source_event_rows"))
    promoted_links = [row for row in candidate_links if _text(row.get("promotion_status")) == "promoted"]
    cross_doc_edges = [
        row for row in ordering_edges if "inferred_from_source_backed_overlap" in row.get("support_basis", [])
    ]
    return {
        "source_event_count": len(source_event_rows),
        "source_family_count": len({_text(row.get("source_family")) for row in source_event_rows if _text(row.get("source_family"))}),
        "candidate_link_count": len(candidate_links),
        "promoted_link_count": len(promoted_links),
        "merged_event_count": len(merged_events),
        "ordering_edge_count": len(ordering_edges),
        "cross_document_ordering_edge_count": len(cross_doc_edges),
        "candidate_link_type_counts": dict(
            sorted(Counter(_text(row.get("link_type")) for row in candidate_links if _text(row.get("link_type"))).items())
        ),
    }


def build_cross_source_event_braid(source_family_runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_event_rows = _normalize_source_event_rows(source_family_runs)
    candidate_links = _build_cross_document_candidates(source_event_rows)
    promoted_links = [
        row
        for row in candidate_links
        if _text(row.get("link_type")) == "same_event_as" and _text(row.get("promotion_status")) == "promoted"
    ]
    merged_event_lookup, merged_events = _cluster_promoted_links(source_event_rows, promoted_links)
    ordering_edges = _build_ordering_edges(source_event_rows, merged_event_lookup)
    collapse_points = [
        {
            "collapse_kind": "merged_event",
            "merged_event_id": row["merged_event_id"],
            "source_event_count": len(row.get("source_event_ids", [])),
            "source_family_count": len(row.get("source_families", [])),
        }
        for row in merged_events
        if len(row.get("source_event_ids", [])) > 1
    ]
    payload = {
        "schema_version": CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION,
        "source_event_rows": source_event_rows,
        "candidate_links": candidate_links,
        "merged_events": merged_events,
        "ordering_edges": ordering_edges,
        "collapse_points": collapse_points,
    }
    payload["summary"] = summarize_cross_source_event_braid(payload)
    return payload


__all__ = [
    "CROSS_SOURCE_EVENT_BRAID_SCHEMA_VERSION",
    "build_cross_source_event_braid",
    "summarize_cross_source_event_braid",
]
