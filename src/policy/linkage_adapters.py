from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_linkage_node(
    *,
    node_id: str,
    layer: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": _text(node_id),
        "layer": _text(layer),
        "label": _text(label),
        "metadata": deepcopy(dict(metadata or {})),
    }


def build_linkage_edge(
    *,
    source: str,
    target: str,
    kind: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": _text(source),
        "target": _text(target),
        "kind": _text(kind),
        "metadata": deepcopy(dict(metadata or {})),
    }


def build_linkage_fragment(
    *,
    nodes: Sequence[Mapping[str, Any]] = (),
    edges: Sequence[Mapping[str, Any]] = (),
    expected_anchor_ids: Sequence[str] = (),
    expected_terminal_ids: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "nodes": [deepcopy(dict(row)) for row in nodes if isinstance(row, Mapping)],
        "edges": [deepcopy(dict(row)) for row in edges if isinstance(row, Mapping)],
        "expected_anchor_ids": [_text(value) for value in expected_anchor_ids if _text(value)],
        "expected_terminal_ids": [_text(value) for value in expected_terminal_ids if _text(value)],
        "notes": [_text(value) for value in notes if _text(value)],
    }


def build_projection_adapter_fragment(
    *,
    layer: str,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    source_id: str | None = None,
    source_edge_kind: str = "adapter_projection",
    source_edge_metadata: Mapping[str, Any] | None = None,
    target_id: str | None = None,
    edge_kind: str = "adapter_projection",
    edge_metadata: Mapping[str, Any] | None = None,
    expected_anchor_ids: Sequence[str] = (),
    expected_terminal_ids: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    nodes = [
        build_linkage_node(
            node_id=node_id,
            layer=layer,
            label=label,
            metadata=metadata,
        )
    ]
    edges = []
    if _text(source_id):
        edges.append(
            build_linkage_edge(
                source=source_id or "",
                target=node_id,
                kind=source_edge_kind,
                metadata=source_edge_metadata,
            )
        )
    if _text(target_id):
        edges.append(
            build_linkage_edge(
                source=node_id,
                target=target_id or "",
                kind=edge_kind,
                metadata=edge_metadata,
            )
        )
    return build_linkage_fragment(
        nodes=nodes,
        edges=edges,
        expected_anchor_ids=expected_anchor_ids,
        expected_terminal_ids=expected_terminal_ids,
        notes=notes,
    )


def build_collection_adapter_fragment(
    *,
    layer: str,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "adapter_projection",
    edge_metadata: Mapping[str, Any] | None = None,
    expected_anchor_ids: Sequence[str] = (),
    expected_terminal_ids: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    nodes = [
        build_linkage_node(
            node_id=node_id,
            layer=layer,
            label=label,
            metadata=metadata,
        )
    ]
    edges = [
        build_linkage_edge(
            source=source_id,
            target=node_id,
            kind=edge_kind,
            metadata=edge_metadata,
        )
        for source_id in upstream_node_ids
        if _text(source_id)
    ]
    return build_linkage_fragment(
        nodes=nodes,
        edges=edges,
        expected_anchor_ids=expected_anchor_ids,
        expected_terminal_ids=expected_terminal_ids,
        notes=notes,
    )


def merge_linkage_fragments(*fragments: Mapping[str, Any]) -> dict[str, Any]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    anchor_ids: list[str] = []
    terminal_ids: list[str] = []
    notes: list[str] = []

    for fragment in fragments:
        if not isinstance(fragment, Mapping):
            continue
        for node in fragment.get("nodes", []):
            if not isinstance(node, Mapping):
                continue
            node_id = _text(node.get("id"))
            if node_id:
                nodes_by_id[node_id] = deepcopy(dict(node))
        for edge in fragment.get("edges", []):
            if not isinstance(edge, Mapping):
                continue
            key = (
                _text(edge.get("source")),
                _text(edge.get("target")),
                _text(edge.get("kind")),
            )
            if all(key):
                edges_by_key[key] = deepcopy(dict(edge))
        for value in fragment.get("expected_anchor_ids", []):
            text = _text(value)
            if text and text not in anchor_ids:
                anchor_ids.append(text)
        for value in fragment.get("expected_terminal_ids", []):
            text = _text(value)
            if text and text not in terminal_ids:
                terminal_ids.append(text)
        for value in fragment.get("notes", []):
            text = _text(value)
            if text and text not in notes:
                notes.append(text)

    return build_linkage_fragment(
        nodes=sorted(nodes_by_id.values(), key=lambda row: (_text(row.get("layer")), _text(row.get("id")))),
        edges=sorted(
            edges_by_key.values(),
            key=lambda row: (_text(row.get("source")), _text(row.get("target")), _text(row.get("kind"))),
        ),
        expected_anchor_ids=anchor_ids,
        expected_terminal_ids=terminal_ids,
        notes=notes,
    )


def build_source_adapter_fragment(
    *,
    anchor_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    target_id: str | None = None,
    edge_kind: str = "source_anchor_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_projection_adapter_fragment(
        layer="source_anchor",
        node_id=anchor_id,
        label=label,
        metadata=metadata,
        target_id=target_id,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
        expected_anchor_ids=[anchor_id],
    )


def build_document_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    target_id: str | None = None,
    edge_kind: str = "document_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_projection_adapter_fragment(
        layer="source_container",
        node_id=node_id,
        label=label,
        metadata=metadata,
        target_id=target_id,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_parse_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    target_id: str | None = None,
    edge_kind: str = "parse_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_projection_adapter_fragment(
        layer="parsed_form",
        node_id=node_id,
        label=label,
        metadata=metadata,
        target_id=target_id,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_claim_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    source_id: str | None = None,
    source_edge_kind: str = "parse_candidate_projection",
    source_edge_metadata: Mapping[str, Any] | None = None,
    target_id: str | None = None,
    edge_kind: str = "candidate_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_projection_adapter_fragment(
        layer="domain_candidate",
        node_id=node_id,
        label=label,
        metadata=metadata,
        source_id=source_id,
        source_edge_kind=source_edge_kind,
        source_edge_metadata=source_edge_metadata,
        target_id=target_id,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_coalescence_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "coalescence_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_collection_adapter_fragment(
        layer="review_surface",
        node_id=node_id,
        label=label,
        metadata=metadata,
        upstream_node_ids=upstream_node_ids,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_authority_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "authority_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_collection_adapter_fragment(
        layer="authority_surface",
        node_id=node_id,
        label=label,
        metadata=metadata,
        upstream_node_ids=upstream_node_ids,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_external_bridge_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "external_bridge_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_collection_adapter_fragment(
        layer="external_candidate",
        node_id=node_id,
        label=label,
        metadata=metadata,
        upstream_node_ids=upstream_node_ids,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_review_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "review_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_coalescence_adapter_fragment(
        node_id=node_id,
        label=label,
        metadata=metadata,
        upstream_node_ids=upstream_node_ids,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
    )


def build_tranche_adapter_fragment(
    *,
    node_id: str,
    label: str,
    metadata: Mapping[str, Any] | None = None,
    upstream_node_ids: Sequence[str] = (),
    edge_kind: str = "workflow_tranche_projection",
    edge_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_collection_adapter_fragment(
        layer="tranche_anchor",
        node_id=node_id,
        label=label,
        metadata=metadata,
        upstream_node_ids=upstream_node_ids,
        edge_kind=edge_kind,
        edge_metadata=edge_metadata,
        expected_terminal_ids=[node_id],
    )


__all__ = [
    "build_authority_adapter_fragment",
    "build_claim_adapter_fragment",
    "build_collection_adapter_fragment",
    "build_coalescence_adapter_fragment",
    "build_document_adapter_fragment",
    "build_external_bridge_adapter_fragment",
    "build_linkage_edge",
    "build_linkage_fragment",
    "build_linkage_node",
    "build_parse_adapter_fragment",
    "build_projection_adapter_fragment",
    "build_review_adapter_fragment",
    "build_source_adapter_fragment",
    "build_tranche_adapter_fragment",
    "merge_linkage_fragments",
]
