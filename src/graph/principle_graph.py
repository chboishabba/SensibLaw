"""Utilities for visualising principle-to-authority relationships."""

from __future__ import annotations

from typing import Any, Dict, Hashable, List, Optional, Set, Tuple


def _freeze_value(value: Any) -> Hashable:
    """Convert metadata values into hashable representations."""

    if isinstance(value, dict):
        return tuple((key, _freeze_value(inner)) for key, inner in sorted(value.items()))
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _freeze_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Tuple[Tuple[str, Hashable], ...]]:
    """Produce a stable, hashable key for edge metadata."""

    if not metadata:
        return None
    return tuple((key, _freeze_value(value)) for key, value in sorted(metadata.items()))


def build_principle_graph(provision: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Build a graph payload linking principles, issues, and authorities.

    Parameters
    ----------
    provision:
        Provision payload as returned by :func:`fetch_provision_atoms`.

    Returns
    -------
    dict
        Dictionary containing ``nodes`` and ``edges`` lists that describe the
        relationship graph.  Nodes include the provision, extracted principles,
        related issues/facts, and linked authorities (cases or statutes).
    """

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    seen_nodes: Dict[str, Dict[str, Any]] = {}
    seen_edges: Set[Tuple[str, str, Optional[str], Optional[Tuple[Tuple[str, Hashable], ...]]]] = set()

    def _add_node(node: Dict[str, Any]) -> Dict[str, Any]:
        node_id = str(node["id"])
        existing = seen_nodes.get(node_id)
        if existing:
            new_meta = node.get("metadata") or {}
            if new_meta:
                existing_meta = existing.setdefault("metadata", {})
                for key, value in new_meta.items():
                    if value is not None and key not in existing_meta:
                        existing_meta[key] = value
            if node.get("kind") and not existing.get("kind"):
                existing["kind"] = node["kind"]
            return existing

        node_copy = dict(node)
        metadata = node_copy.get("metadata")
        if metadata is None:
            node_copy["metadata"] = {}
        nodes.append(node_copy)
        seen_nodes[node_id] = node_copy
        return node_copy

    def _add_edge(edge: Dict[str, Any]) -> None:
        source = str(edge["source"])
        target = str(edge["target"])
        label = edge.get("label")
        metadata_key = _freeze_metadata(edge.get("metadata"))
        key = (
            source,
            target,
            str(label) if label is not None else None,
            metadata_key,
        )
        if key in seen_edges:
            return
        edge_copy = dict(edge)
        metadata = edge_copy.get("metadata")
        if metadata is None:
            edge_copy["metadata"] = {}
        edges.append(edge_copy)
        seen_edges.add(key)

    provision_id = str(
        provision.get("provision_id")
        or provision.get("id")
        or provision.get("identifier")
        or "Provision"
    )
    provision_label = str(provision.get("title") or provision_id)
    _add_node(
        {
            "id": provision_id,
            "label": provision_label,
            "kind": "provision",
            "metadata": {
                key: provision[key]
                for key in ("provision_id", "identifier", "title")
                if provision.get(key)
            },
        }
    )

    atoms = provision.get("atoms") or []
    for index, atom in enumerate(atoms):
        role = (atom.get("role") or "").lower()
        if role != "principle":
            continue

        principle_payload = atom.get("principle") or {}
        principle_id = str(
            principle_payload.get("id")
            or atom.get("id")
            or atom.get("label")
            or f"{provision_id}::principle{index + 1}"
        )
        principle_label = str(
            principle_payload.get("title")
            or atom.get("label")
            or principle_id
        )

        principle_metadata: Dict[str, Any] = {}
        summary = principle_payload.get("summary")
        if summary and summary != principle_label:
            principle_metadata["summary"] = summary
        tags = principle_payload.get("tags")
        if tags:
            principle_metadata["tags"] = list(tags)

        proof = atom.get("proof") or {}
        if proof:
            status = proof.get("status")
            if status:
                principle_metadata["status"] = str(status)
            confidence = proof.get("confidence")
            if confidence is not None:
                principle_metadata["confidence"] = confidence
            evidence = proof.get("evidenceCount")
            if evidence is not None:
                principle_metadata["evidence_count"] = evidence

        _add_node(
            {
                "id": principle_id,
                "label": principle_label,
                "kind": "principle",
                "metadata": principle_metadata,
            }
        )
        _add_edge({"source": provision_id, "target": principle_id, "label": "principle"})

        for child_index, child in enumerate(atom.get("children") or []):
            child_id = str(
                child.get("id")
                or child.get("label")
                or f"{principle_id}::issue{child_index + 1}"
            )
            child_label = str(child.get("label") or child_id)
            child_role = str(child.get("role") or "issue")
            child_kind = child_role.lower() or "issue"
            child_metadata: Dict[str, Any] = {"role": child_role}

            child_proof = child.get("proof") or {}
            if child_proof:
                status = child_proof.get("status")
                if status:
                    child_metadata["status"] = str(status)
                confidence = child_proof.get("confidence")
                if confidence is not None:
                    child_metadata["confidence"] = confidence
                evidence = child_proof.get("evidenceCount")
                if evidence is not None:
                    child_metadata["evidence_count"] = evidence

            notes = child.get("notes")
            if notes:
                child_metadata["notes"] = notes

            _add_node(
                {
                    "id": child_id,
                    "label": child_label,
                    "kind": child_kind,
                    "metadata": child_metadata,
                }
            )
            _add_edge(
                {
                    "source": principle_id,
                    "target": child_id,
                    "label": child_role or "issue",
                    "kind": child_kind,
                }
            )

        authorities = principle_payload.get("authorities") or []
        for auth_index, authority in enumerate(authorities):
            auth_id = str(
                authority.get("id")
                or authority.get("citation")
                or f"{principle_id}::authority{auth_index + 1}"
            )
            auth_label = str(
                authority.get("title")
                or authority.get("id")
                or authority.get("citation")
                or auth_id
            )
            auth_type = str(authority.get("type") or "").lower()
            if not auth_type:
                if auth_id.startswith("Case#"):
                    auth_type = "case"
                elif auth_id.startswith("Provision#") or auth_id.startswith("Statute#"):
                    auth_type = "statute"
                else:
                    auth_type = "authority"

            authority_metadata: Dict[str, Any] = {}
            for key in ("citation", "pinpoint", "relationship"):
                value = authority.get(key)
                if value:
                    authority_metadata[key] = value
            tags = authority.get("tags")
            if tags:
                authority_metadata["tags"] = list(tags)

            _add_node(
                {
                    "id": auth_id,
                    "label": auth_label,
                    "kind": auth_type,
                    "metadata": authority_metadata,
                }
            )

            edge_metadata: Dict[str, Any] = {}
            if authority.get("pinpoint"):
                edge_metadata["pinpoint"] = authority["pinpoint"]

            edge_label = str(authority.get("relationship") or "authority")
            _add_edge(
                {
                    "source": principle_id,
                    "target": auth_id,
                    "label": edge_label,
                    "kind": auth_type or "authority",
                    "metadata": edge_metadata,
                }
            )

    return {"nodes": nodes, "edges": edges}


__all__ = ["build_principle_graph"]

