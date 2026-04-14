from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from collections import defaultdict
from typing import Any, Callable, Mapping, Optional, Sequence

try:
    from src.fact_intake.control_plane import (
        build_follow_control_plane,
        build_follow_queue_item,
        summarize_follow_queue,
    )
except ModuleNotFoundError:
    from fact_intake.control_plane import (  # type: ignore[no-redef]
        build_follow_control_plane,
        build_follow_queue_item,
        summarize_follow_queue,
    )

try:
    from SensibLaw.src.sources.eur_lex_adapter import CELEX_METADATA, EurLexHierarchyAdapter
except ModuleNotFoundError:
    from sources.eur_lex_adapter import CELEX_METADATA, EurLexHierarchyAdapter

try:
    from src.ontology.debate_follow_contract import build_sample_debate_records
except ModuleNotFoundError:
    from ontology.debate_follow_contract import build_sample_debate_records


GWB_LEGAL_FOLLOW_GRAPH_VERSION = "gwb.legal_follow_graph.v1"
_LEGAL_CITE_FAMILY_BY_DOMAIN = {
    "legislation.gov.uk": "uk_legislation",
    "eur-lex.europa.eu": "eur_lex",
    "bailii.org": "bailii",
    "parliament.uk": "uk_parliament",
    "gov.uk": "uk_government",
}
_BREXIT_TOKENS = (
    "brexit",
    "uk-eu",
    "article 50",
    "withdrawal agreement",
    "european union (withdrawal)",
    "eu withdrawal",
)
_AUTHORITY_YIELD_BY_CITE_CLASS = {
    "uk_legislation": ("high", 5),
    "eur_lex": ("high", 5),
    "bailii": ("medium", 4),
    "uk_parliament": ("medium", 3),
    "uk_government": ("medium", 3),
    "uk-eu": ("medium", 3),
    "eu-law": ("medium", 3),
    "uk-domestic": ("medium", 3),
    "general": ("low", 1),
}


@lru_cache(maxsize=1)
def _foundation_source_catalog() -> tuple[dict[str, str], ...]:
    path = Path(__file__).resolve().parents[1] / "data" / "foundation_sources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("sources") if isinstance(payload, Mapping) else []
    catalog: list[dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip()
        base_url = str(row.get("base_url") or "").strip()
        jurisdiction = str(row.get("jurisdiction") or "").strip()
        if not name or not base_url:
            continue
        catalog.append({"name": name, "base_url": base_url, "jurisdiction": jurisdiction})
    return tuple(catalog)


def _slug(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())
    return cleaned.strip("_").lower() or "unknown"


def _merge_unique(values: list[str], incoming: Sequence[str]) -> list[str]:
    merged = list(values)
    for value in incoming:
        normalized = str(value or "").strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _normalize_typing_signal(signal: Mapping[str, Any], *, default_source: str) -> dict[str, Any]:
    if not isinstance(signal, Mapping):
        return {}
    entry = dict(signal)
    entry.setdefault("signal_id", f"{default_source}:{str(entry.get('linked_seed_id') or entry.get('source_row_id') or 'typing')}")
    entry.setdefault("source", default_source)
    entry.setdefault("signal_kind", "missing_instance_of_typing_deficit")
    return entry


def _collect_gwb_typing_deficit_signals(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        extra_signals = row.get("typing_deficit_signals") or []
        if isinstance(extra_signals, Sequence):
            for signal in extra_signals:
                normalized = _normalize_typing_signal(signal, default_source="gwb")
                if normalized:
                    signals.append(normalized)
        elif row.get("missing_instance_of_typing_deficit") or row.get("typing_deficit_reason"):
            signals.append(
                _normalize_typing_signal(
                    {
                        "source_row_id": row.get("source_row_id"),
                        "linked_seed_id": row.get("seed_id"),
                        "details": row.get("typing_deficit_reason") or row.get("review_status"),
                    },
                    default_source="gwb",
                )
            )
    return signals


def _label_counts(nodes: Sequence[Mapping[str, Any]], *, kind: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in nodes:
        if str(row.get("kind") or "").strip() != kind:
            continue
        label = str(row.get("label") or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _source_kind_counts(nodes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in nodes:
        node_id = str(row.get("id") or "").strip()
        if not node_id.startswith("source:"):
            continue
        kind = str(row.get("kind") or "").strip() or "source_row"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _followed_source_url(receipt: Mapping[str, Any]) -> str | None:
    if not isinstance(receipt, Mapping):
        return None
    for key in ("source_url", "url", "link", "href", "value"):
        raw = str(receipt.get(key) or "").strip()
        if raw and raw.lower().startswith(("http://", "https://")):
            return raw
    return None


def _cite_classification(receipt: Mapping[str, Any], *, url: str | None = None, source_text: str | None = None) -> str:
    url_text = str(url or "").strip().lower()
    for domain, family in _LEGAL_CITE_FAMILY_BY_DOMAIN.items():
        if domain in url_text:
            return family
    hints = [
        str(receipt.get("kind") or ""),
        str(receipt.get("label") or ""),
        str(receipt.get("value") or ""),
        str(source_text or ""),
        url_text,
    ]
    content = " ".join(word.strip().lower() for word in hints if word.strip())
    if any(token in content for token in _BREXIT_TOKENS):
        return "uk-eu"
    if "uk" in content or "british" in content or "parliament" in content or "house of commons" in content:
        return "uk-domestic"
    if "eu" in content or "european" in content or "commission" in content:
        return "eu-law"
    return "general"


def _is_brexit_related(receipt: Mapping[str, Any], *, url: str | None = None, source_text: str | None = None) -> bool:
    hints = [
        str(receipt.get("kind") or ""),
        str(receipt.get("label") or ""),
        str(receipt.get("value") or ""),
        str(source_text or ""),
        str(url or ""),
    ]
    content = " ".join(word.strip().lower() for word in hints if word.strip())
    return any(token in content for token in _BREXIT_TOKENS)


def _edge_metadata_label_counts(
    edges: Sequence[Mapping[str, Any]], *, kind: str, metadata_key: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        if str(edge.get("kind") or "") != kind:
            continue
        metadata = edge.get("metadata") if isinstance(edge.get("metadata"), Mapping) else {}
        label = str(metadata.get(metadata_key) or "").strip()
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
    return counts


def _cite_class_counts(nodes: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        if node.get("kind") != "followed_source":
            continue
        metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
        cite_class = str(metadata.get("cite_class") or "").strip() or "general"
        counts[cite_class] = counts.get(cite_class, 0) + 1
    return counts


def _brexit_follow_count(nodes: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for node in nodes:
        if node.get("kind") != "followed_source":
            continue
        metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
        if bool(metadata.get("brexit_related")):
            count += 1
    return count


def _has_eur_lex_node(nodes: Sequence[Mapping[str, Any]]) -> bool:
    for node in nodes:
        if node.get("kind") != "followed_source":
            continue
        metadata = node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}
        if str(metadata.get("cite_class") or "").strip() == "eur_lex":
            return True
    return False


def _inject_deterministic_eur_lex_nodes(
    add_node: Callable[..., None],
    add_edge: Callable[..., None],
) -> None:
    if not CELEX_METADATA:
        return
    catalog_node = "source_family:eur_lex_deterministic"
    add_node(
        catalog_node,
        kind="source_family",
        label="EUR-Lex deterministic catalog",
        metadata={"source_family": "eur_lex", "deterministic": True},
    )
    adapter = EurLexHierarchyAdapter()
    for celex_id, entry in CELEX_METADATA.items():
        result = adapter.fetch(celex_id)
        payload = json.loads(result.content.decode("utf-8"))
        node_id = f"followed_source:eur_lex:{_slug(celex_id)}"
        add_node(
            node_id,
            kind="followed_source",
            label=payload.get("live_title") or payload.get("title") or f"EUR-Lex {celex_id}",
            metadata={
                "source_url": payload.get("canonical_url"),
                "cite_class": "eur_lex",
                "receipt_kind": "eur_lex_catalog",
                "brexit_related": True,
                "celex_id": celex_id,
                "resolution_mode": result.metadata.get("resolution_mode"),
                "live_title": payload.get("live_title"),
            },
        )
        add_edge(
            catalog_node,
            node_id,
            kind="follows_source",
            metadata={
                "receipt_kind": "eur_lex_catalog",
                "source_url": payload.get("canonical_url"),
                "celex_id": celex_id,
            },
        )


def _gwb_follow_priority(
    *,
    cite_class: str,
    brexit_related: bool,
    source_ref_count: int,
) -> tuple[int, str]:
    authority_yield, base_score = _AUTHORITY_YIELD_BY_CITE_CLASS.get(cite_class, ("low", 1))
    score = base_score
    if brexit_related:
        score += 3
    if source_ref_count >= 2:
        score += 1
    return score, authority_yield


def _foundation_source_receipts(row: Mapping[str, Any], existing_urls: set[str]) -> list[dict[str, str]]:
    text = " ".join(
        str(value or "").strip()
        for value in (row.get("text"), row.get("source_family"), row.get("source_row_id"))
        if str(value or "").strip()
    ).casefold()
    if not text:
        return []
    receipts: list[dict[str, str]] = []
    for source in _foundation_source_catalog():
        name = str(source.get("name") or "").strip()
        base_url = str(source.get("base_url") or "").strip()
        if not name or not base_url or base_url in existing_urls:
            continue
        if name.casefold() not in text:
            continue
        receipts.append(
            {
                "kind": "foundation_source_reference",
                "label": name,
                "value": base_url,
            }
        )
    return receipts


def build_gwb_legal_follow_operator_view(graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    summary = dict(graph.get("summary", {})) if isinstance(graph.get("summary"), Mapping) else {}
    typing_signals = graph.get("typing_deficit_signals") if isinstance(graph.get("typing_deficit_signals"), list) else []
    highlights = [
        {
            "id": str(row.get("id") or ""),
            "kind": str(row.get("kind") or ""),
            "label": str(row.get("label") or ""),
        }
        for row in nodes
        if str(row.get("kind") or "") in {"source_family", "linkage_kind", "support_kind", "review_status", "predicate"}
    ][:8]
    node_map = {str(row.get("id") or ""): row for row in nodes if str(row.get("id") or "").strip()}
    follow_source_links: dict[str, list[dict[str, str]]] = {}
    for edge in edges:
        if str(edge.get("kind") or "") != "follows_source":
            continue
        source_id = str(edge.get("source") or "").strip()
        target_id = str(edge.get("target") or "").strip()
        if not source_id or not target_id:
            continue
        source_row = node_map.get(source_id) or {}
        metadata = edge.get("metadata") if isinstance(edge.get("metadata"), Mapping) else {}
        follow_source_links.setdefault(target_id, []).append(
            {
                "source_row_id": str(source_row.get("metadata", {}).get("source_row_id") or ""),
                "source_label": str(source_row.get("label") or source_id),
                "receipt_kind": str(metadata.get("receipt_kind") or ""),
            }
        )
    sample_edges = [
        {
            "kind": str(row.get("kind") or ""),
            "source": str((node_map.get(str(row.get("source") or "")) or {}).get("label") or row.get("source") or ""),
            "target": str((node_map.get(str(row.get("target") or "")) or {}).get("label") or row.get("target") or ""),
        }
        for row in edges[:8]
    ]
    queue: list[dict[str, Any]] = []
    for row in nodes:
        if str(row.get("kind") or "") != "followed_source":
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        source_url = str(metadata.get("source_url") or "").strip()
        cite_class = str(metadata.get("cite_class") or "").strip() or "general"
        brexit_related = bool(metadata.get("brexit_related"))
        source_refs = follow_source_links.get(str(row.get("id") or ""), [])
        route_target = {
            "uk_legislation": "uk_legislation_follow",
            "eur_lex": "eur_lex_follow",
            "bailii": "citation_follow",
            "uk_parliament": "uk_parliament_follow",
            "uk_government": "uk_government_follow",
        }.get(cite_class, "manual_review")
        priority_score, authority_yield = _gwb_follow_priority(
            cite_class=cite_class,
            brexit_related=brexit_related,
            source_ref_count=len(source_refs),
        )
        chips = [cite_class]
        if brexit_related:
            chips.append("brexit_related")
        live_title = str(metadata.get("live_title") or "").strip()
        resolution_mode = str(metadata.get("resolution_mode") or "static_catalog").strip()
        title_value = live_title or str(row.get("label") or source_url or "GWB legal follow")
        if resolution_mode == "live":
            priority_score += 1
            chips.append("live_resolved")
        follow_item = build_follow_queue_item(
            item_id=str(row.get("id") or ""),
            title=title_value,
            subtitle="follow_needed_conjecture",
            description=(
                "Derived GWB legal-follow candidate requiring bounded local-first authority review."
            ),
            conjecture_kind="follow_needed_conjecture",
            route_target=route_target,
            resolution_status="open",
            chips=chips,
            detail_rows=[
                {"label": "Source URL", "value": source_url},
                {"label": "Cite class", "value": cite_class},
                {"label": "Authority yield", "value": authority_yield},
                {"label": "Brexit related", "value": "yes" if brexit_related else "no"},
                {
                    "label": "Source rows",
                    "value": ", ".join(
                        source_ref["source_row_id"] or source_ref["source_label"]
                        for source_ref in source_refs
                    ) or "none",
                },
                {"label": "Resolution mode", "value": resolution_mode},
                {"label": "Live title", "value": live_title or "(none)"},
            ],
            extra={
                "source_url": source_url,
                "cite_class": cite_class,
                "priority_score": priority_score,
                "authority_yield": authority_yield,
                "brexit_related": brexit_related,
                "source_refs": source_refs,
                "resolution_mode": resolution_mode,
                "live_title": live_title,
                "receipt_kind_counts": {
                    key: len([ref for ref in source_refs if ref.get("receipt_kind") == key])
                    for key in sorted(
                        {ref.get("receipt_kind") for ref in source_refs if ref.get("receipt_kind")}
                    )
                },
            },
        )
        follow_item["priority_score"] = priority_score
        queue.append(follow_item)
    queue.sort(
        key=lambda row: (
            -int(row.get("priority_score") or 0),
            str(row.get("route_target") or ""),
            str(row.get("title") or ""),
        )
    )
    for index, row in enumerate(queue, start=1):
        row["priority_rank"] = index
    queue_summary = summarize_follow_queue(queue)
    priority_band_counts = {"high": 0, "medium": 0, "low": 0}
    highest_priority_score = 0
    highest_authority_yield = "low"
    for row in queue:
        authority_yield = str(row.get("authority_yield") or "low")
        if authority_yield not in priority_band_counts:
            priority_band_counts[authority_yield] = 0
        priority_band_counts[authority_yield] += 1
        score = int(row.get("priority_score") or 0)
        if score > highest_priority_score:
            highest_priority_score = score
            highest_authority_yield = authority_yield
    return {
        "available": bool(nodes),
        "control_plane": build_follow_control_plane(
            source_family="gwb_legal_follow",
            hint_kind="legal_follow_hint",
            receipt_kind="followed_source",
            substrate_kind="legal_follow_graph",
            conjecture_kind="follow_needed_conjecture",
            route_targets=list(queue_summary["route_target_counts"].keys()) or [
                "citation_follow",
                "uk_legislation_follow",
                "eur_lex_follow",
                "manual_review",
            ],
            resolution_statuses=list(queue_summary["resolution_status_counts"].keys()) or [
                "open",
                "resolved",
                "reviewed",
            ],
        ),
        "summary": {
            **summary,
            "route_target_counts": queue_summary["route_target_counts"],
            "resolution_status_counts": queue_summary["resolution_status_counts"],
            "queue_count": queue_summary["queue_count"],
            "priority_band_counts": priority_band_counts,
            "highest_priority_score": highest_priority_score,
            "highest_authority_yield": highest_authority_yield,
        },
        "highlight_nodes": highlights,
        "sample_edges": sample_edges,
        "queue": queue,
        "typing_deficit_signals": typing_signals,
    }


def build_gwb_legal_follow_graph(
    *,
    review_item_rows: Sequence[Mapping[str, Any]],
    source_review_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_index: dict[str, dict[str, Any]] = {}
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, *, kind: str, label: str, metadata: Mapping[str, Any] | None = None) -> None:
        clean_metadata = {key: value for key, value in dict(metadata or {}).items() if value not in (None, "", [], {})}
        if node_id in node_index:
            existing = node_index[node_id]
            merged = dict(existing.get("metadata") or {})
            for key, value in clean_metadata.items():
                if isinstance(value, list):
                    merged[key] = _merge_unique(list(merged.get(key) or []), value)
                elif key not in merged or merged.get(key) in (None, "", [], {}):
                    merged[key] = value
            existing["metadata"] = merged
            return
        node = {"id": node_id, "kind": kind, "label": label, "metadata": clean_metadata}
        node_index[node_id] = node
        nodes.append(node)

    def add_edge(source: str, target: str, *, kind: str, metadata: Mapping[str, Any] | None = None) -> None:
        key = (source, target, kind)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": source, "target": target, "kind": kind, "metadata": dict(metadata or {})})

    def _ensure_debate_target_node(target_id: str) -> None:
        if not target_id or target_id in node_index:
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
                        "instrument_type": target_id.split(":", 1)[0],
                        "edge_label": f"{relation}:{target_id}",
                        "edge_note": f"{relation.capitalize()} reference noted in debate",
                        "edge_context": record.summary,
                    },
                )

    review_by_seed = {
        str(row.get("seed_id") or "").strip(): row
        for row in review_item_rows
        if str(row.get("seed_id") or "").strip()
    }

    for row in review_item_rows:
        seed_id = str(row.get("seed_id") or "").strip()
        if not seed_id:
            continue
        seed_node = f"seed:{_slug(seed_id)}"
        add_node(
            seed_node,
            kind="seed_lane",
            label=str(row.get("action_summary") or seed_id),
            metadata={
                "seed_id": seed_id,
                "coverage_status": str(row.get("coverage_status") or "").strip() or None,
                "linkage_kind": str(row.get("linkage_kind") or "").strip() or None,
                "support_kinds": [str(value) for value in row.get("support_kinds", []) if str(value or "").strip()],
                "review_statuses": [str(value) for value in row.get("review_statuses", []) if str(value or "").strip()],
            },
        )

    for row in source_review_rows:
        seed_id = str(row.get("seed_id") or "").strip()
        source_kind = str(row.get("source_kind") or "").strip()
        source_row_id = str(row.get("source_row_id") or "").strip()
        source_node_id = f"source:{_slug(source_row_id or source_kind)}"
        add_node(
            source_node_id,
            kind=source_kind or "source_row",
            label=str(row.get("text") or row.get("source_family") or source_row_id or "source row"),
            metadata={
                "source_row_id": source_row_id or None,
                "review_status": str(row.get("review_status") or "").strip() or None,
                "primary_workload_class": str(row.get("primary_workload_class") or "").strip() or None,
            },
        )
        if seed_id:
            seed_node = f"seed:{_slug(seed_id)}"
            add_edge(seed_node, source_node_id, kind="supports_source_row", metadata={"seed_id": seed_id})

        family = str(row.get("source_family") or "").strip()
        if family:
            family_node = f"source_family:{_slug(family)}"
            add_node(
                family_node,
                kind="source_family",
                label=family,
                metadata={"source_family": family},
            )
            add_edge(source_node_id, family_node, kind="mentions_source_family", metadata={"source_family": family})

        for anchor in row.get("candidate_anchors", []) or []:
            if not isinstance(anchor, Mapping):
                continue
            anchor_kind = str(anchor.get("anchor_kind") or "").strip()
            anchor_label = str(anchor.get("anchor_label") or anchor.get("anchor_value") or "").strip()
            if not anchor_kind or not anchor_label:
                continue
            if anchor_kind == "predicate":
                node_kind = "predicate"
            elif anchor_kind in {"support_kind", "review_status", "source_family"}:
                node_kind = anchor_kind
            else:
                node_kind = "anchor"
            anchor_node = f"{node_kind}:{_slug(anchor_kind)}:{_slug(anchor_label)}"
            add_node(
                anchor_node,
                kind=node_kind,
                label=anchor_label,
                metadata={"anchor_kind": anchor_kind, "anchor_value": anchor.get("anchor_value")},
            )
            add_edge(
                source_node_id,
                anchor_node,
                kind=f"mentions_{anchor_kind}",
                metadata={"anchor_kind": anchor_kind},
            )

        existing_urls = {
            url
            for receipt in row.get("receipts", []) or []
            for url in [_followed_source_url(receipt)]
            if url
        }
        all_receipts = list(row.get("receipts", []) or []) + _foundation_source_receipts(row, existing_urls)
        for receipt in all_receipts:
            url = _followed_source_url(receipt)
            if not url:
                continue
            receipt_kind = str(receipt.get("kind") or "").strip() or "followed_source"
            cite_class = _cite_classification(receipt, url=url, source_text=str(row.get("text") or ""))
            brexit_related = _is_brexit_related(receipt, url=url, source_text=str(row.get("text") or ""))
            node_id = f"followed_source:{_slug(url)}"
            node_metadata = {
                "source_url": url,
                "receipt_kind": receipt_kind,
                "cite_class": cite_class,
                "brexit_related": brexit_related,
            }
            receipt_metadata = receipt.get("metadata") if isinstance(receipt.get("metadata"), Mapping) else {}
            node_metadata.update(receipt_metadata)
            add_node(
                node_id,
                kind="followed_source",
                label=str(receipt.get("label") or url),
                metadata=node_metadata,
            )
            add_edge(
                source_node_id,
                node_id,
                kind="follows_source",
                metadata={"receipt_kind": receipt_kind, "source_url": url},
            )

        review_row = review_by_seed.get(seed_id)
        linkage_kind = str((review_row or {}).get("linkage_kind") or "").strip()
        if linkage_kind and seed_id:
            linkage_node = f"linkage_kind:{_slug(linkage_kind)}"
            add_node(linkage_node, kind="linkage_kind", label=linkage_kind, metadata={"linkage_kind": linkage_kind})
            add_edge(f"seed:{_slug(seed_id)}", linkage_node, kind="uses_linkage_kind", metadata={"linkage_kind": linkage_kind})

    _inject_debate_records()

    if not _has_eur_lex_node(nodes):
        _inject_deterministic_eur_lex_nodes(add_node, add_edge)

    typing_deficit_signals = _collect_gwb_typing_deficit_signals(source_review_rows)
    return {
        "version": GWB_LEGAL_FOLLOW_GRAPH_VERSION,
        "derived_only": True,
        "challengeable": True,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "seed_lane_count": sum(1 for row in nodes if row["kind"] == "seed_lane"),
            "source_row_count": len(source_review_rows),
            "source_row_node_count": sum(1 for row in nodes if str(row["id"]).startswith("source:")),
            "source_family_count": sum(1 for row in nodes if row["kind"] == "source_family"),
            "predicate_count": sum(1 for row in nodes if row["kind"] == "predicate"),
            "review_status_count": sum(1 for row in nodes if row["kind"] == "review_status"),
            "support_kind_count": sum(1 for row in nodes if row["kind"] == "support_kind"),
            "source_kind_counts": _source_kind_counts(nodes),
            "source_family_label_counts": _label_counts(nodes, kind="source_family"),
            "linkage_kind_counts": _label_counts(nodes, kind="linkage_kind"),
            "review_status_label_counts": _label_counts(nodes, kind="review_status"),
            "support_kind_label_counts": _label_counts(nodes, kind="support_kind"),
            "followed_source_count": sum(1 for row in nodes if row["kind"] == "followed_source"),
            "followed_source_kind_counts": _label_counts(nodes, kind="followed_source"),
            "followed_source_receipt_kind_counts": _edge_metadata_label_counts(
                edges, kind="follows_source", metadata_key="receipt_kind"
            ),
            "followed_source_cite_class_counts": _cite_class_counts(nodes),
            "brexit_related_follow_count": _brexit_follow_count(nodes),
        },
        "typing_deficit_signals": typing_deficit_signals,
    }


__all__ = [
    "GWB_LEGAL_FOLLOW_GRAPH_VERSION",
    "build_gwb_legal_follow_graph",
    "build_gwb_legal_follow_operator_view",
]
