"""Partition-independent semantic parity surfaces and comparisons."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


PARITY_SCHEMA_VERSION = "sensiblaw.semantic-parity.v1"
SEMANTIC_ARTIFACT_KEYS = (
    "annotation_layer",
    "semantic_annotation_layer",
    "relational_bundle",
    "pnf_graph",
    "refined_pnf_graph",
    "semantic_reduction_constraints",
    "constraint_assessments",
    "typed_meets",
    "factor_refinements",
    "resolution_demands",
    "factor_anchors",
    "binding_candidate_sets",
    "binding_candidate_set_builds",
)


def canonical_stream_digest(value: Any) -> str:
    """Hash canonical JSON incrementally rather than creating one giant string."""

    digest = hashlib.sha256()
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    for chunk in encoder.iterencode(value):
        digest.update(chunk.encode("utf-8"))
    return digest.hexdigest()


def artifact_identity(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and value.get("representation") == "manifest":
        return {
            "representation": "manifest",
            "root_ref": str(value.get("root_ref") or ""),
            "ordered_digest": str(value.get("ordered_digest") or ""),
            "record_count": int(value.get("record_count") or 0),
        }
    if value is None:
        return {"representation": "absent"}
    count = len(value) if isinstance(value, (Mapping, list, tuple)) else 1
    return {
        "representation": "materialised",
        "ordered_digest": canonical_stream_digest(value),
        "record_count": count,
    }


def semantic_surface_from_artifacts(
    artifacts: Mapping[str, Any],
    *,
    document_ref: str | None = None,
    build_ref: str | None = None,
    occurrence_ref: str | None = None,
) -> dict[str, Any]:
    annotation_graph = artifacts.get("annotation_graph") or {}
    typing_hierarchies = artifacts.get("typing_hierarchies") or {}
    return {
        "schema_version": PARITY_SCHEMA_VERSION,
        "document_ref": str(document_ref or artifacts.get("document_ref") or ""),
        "annotation_graph_ref": str(
            annotation_graph.get("graph_ref")
            if isinstance(annotation_graph, Mapping)
            else ""
        ),
        "logical_layer_refs": sorted(
            str(row.get("layer_ref") or "")
            for row in artifacts.get("logical_layer_manifests") or ()
            if isinstance(row, Mapping) and row.get("layer_ref")
        ),
        "document_projection_manifest_ref": str(
            (artifacts.get("document_projection_manifest") or {}).get("manifest_ref")
            if isinstance(artifacts.get("document_projection_manifest"), Mapping)
            else ""
        ),
        "logical_typing_refs": sorted(
            str(row.get("logical_typing_ref") or "")
            for row in (
                typing_hierarchies.values()
                if isinstance(typing_hierarchies, Mapping)
                else ()
            )
            if isinstance(row, Mapping) and row.get("logical_typing_ref")
        ),
        "artifact_identities": {
            key: artifact_identity(artifacts.get(key))
            for key in SEMANTIC_ARTIFACT_KEYS
            if key in artifacts
        },
        "stage_build_keys": dict(artifacts.get("stage_build_keys") or {}),
        "build_ref": build_ref,
        "occurrence_ref": occurrence_ref,
        "physical_partition_fields_excluded": [
            "root_graph_ref",
            "hierarchy_node_ref",
            "leaf_capacity",
            "worker_count",
            "completion_order",
        ],
    }


def semantic_surface_from_execution_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    amplification = receipt.get("amplification") or {}
    identity = amplification.get("identity_receipt") or {}
    typing = receipt.get("typing_hierarchies") or {}
    return {
        "schema_version": PARITY_SCHEMA_VERSION,
        "document_ref": str(receipt.get("document_ref") or ""),
        "annotation_graph_ref": str(identity.get("annotation_graph_ref") or ""),
        "logical_layer_refs": sorted(identity.get("logical_layer_refs") or ()),
        "document_projection_manifest_ref": str(
            identity.get("document_projection_manifest_ref") or ""
        ),
        "logical_typing_refs": sorted(
            str(value.get("logical_typing_ref") or "")
            for value in typing.values()
            if isinstance(value, Mapping) and value.get("logical_typing_ref")
        ),
        "artifact_identities": dict(identity.get("manifest_descriptors") or {}),
        "stage_build_keys": dict(identity.get("stage_build_keys") or {}),
        "build_ref": identity.get("build_ref"),
        "occurrence_ref": identity.get("occurrence_ref"),
        "physical_partition_fields_excluded": [
            "root_graph_ref",
            "hierarchy_node_ref",
            "leaf_capacity",
            "worker_count",
            "completion_order",
        ],
    }


def compare_semantic_surfaces(
    surfaces: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(surfaces) < 2:
        raise ValueError("semantic parity requires at least two surfaces")
    normalized = [dict(surface) for surface in surfaces]
    fields = (
        "document_ref",
        "annotation_graph_ref",
        "logical_layer_refs",
        "document_projection_manifest_ref",
        "logical_typing_refs",
        "artifact_identities",
        "stage_build_keys",
    )
    field_results = {
        field: all(
            surface.get(field) == normalized[0].get(field) for surface in normalized[1:]
        )
        for field in fields
    }
    optional_publication = {
        field: all(
            surface.get(field) == normalized[0].get(field) for surface in normalized[1:]
        )
        for field in ("build_ref", "occurrence_ref")
        if all(surface.get(field) is not None for surface in normalized)
    }
    return {
        "schema_version": PARITY_SCHEMA_VERSION,
        "surface_count": len(normalized),
        "field_parity": field_results,
        "publication_parity": optional_publication,
        "semantic_parity": all(field_results.values()),
        "publication_identity_compared": bool(optional_publication),
        "partition_layout_has_semantic_effect": not all(field_results.values()),
        "surfaces": normalized,
    }


__all__ = [
    "PARITY_SCHEMA_VERSION",
    "SEMANTIC_ARTIFACT_KEYS",
    "artifact_identity",
    "canonical_stream_digest",
    "compare_semantic_surfaces",
    "semantic_surface_from_artifacts",
    "semantic_surface_from_execution_receipt",
]
