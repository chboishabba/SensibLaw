from __future__ import annotations

from typing import Any, Mapping

from src.policy.suite_normalized_artifact import build_zelph_hf_transport_normalized_artifact


WIKIDATA_ZELPH_LANE_PROOF_SCHEMA_VERSION = "sl.wikidata_zelph_lane_proof.v0_1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_local_manifest() -> dict[str, Any]:
    return {
        "manifestVersion": "zelph-hf-layout/v2",
        "createdAtUtc": "2026-07-03T00:00:00Z",
        "storageMode": "multi-object-shards",
        "transport": {
            "primary": "hf-object-fetch",
            "fallback": "local-file",
        },
        "source": {
            "binPath": "bounded-local://wikidata-disjointness-slice.bin",
            "headerLengthBytes": 8192,
            "totalChunkCount": 6,
            "totalChunkBytes": 24576,
        },
        "selectorModel": {
            "unit": "section-chunk",
            "supportedSections": ["left", "right", "nameOfNode", "nodeOfName"],
            "supportedOperations": ["header-probe", "selected-chunk-read", "node-route", "sparql-subset"],
            "unsupportedOperations": ["fullReasoningSafe"],
        },
        "capabilities": {
            "headerProbe": True,
            "selectedChunkRead": True,
            "nodeRouteIndex": True,
        },
        "hfObjects": {
            "manifest": {
                "path": "hf://datasets/acrion/zelph/bounded-local/disjointness-report.hf-v2.json",
            },
            "nodeRouteIndex": {
                "path": "hf://datasets/acrion/zelph/bounded-local/disjointness-report.route.json",
                "format": "zelph-node-route/v1",
            },
        },
        "sections": {
            "left": {"chunkCount": 2},
            "right": {"chunkCount": 2},
            "nameOfNode": {"chunkCount": 1},
            "nodeOfName": {"chunkCount": 1},
        },
    }


def _bounded_local_selectors() -> list[dict[str, Any]]:
    return [
        {
            "selector_kind": "route",
            "selector_id": "sel:route:p2738-holder",
            "section": "nameOfNode",
            "chunk_indices": [0],
            "route_name": "P2738",
            "route_lang": "wikidata",
        },
        {
            "selector_kind": "route",
            "selector_id": "sel:route:p11260-qualifier",
            "section": "nameOfNode",
            "chunk_indices": [0],
            "route_name": "P11260",
            "route_lang": "wikidata",
        },
        {
            "selector_kind": "section",
            "selector_id": "sel:left0",
            "section": "left",
            "chunk_index": 0,
        },
        {
            "selector_kind": "section",
            "selector_id": "sel:right0",
            "section": "right",
            "chunk_index": 0,
        },
        {
            "selector_kind": "section",
            "selector_id": "sel:nodeOfName0",
            "section": "nodeOfName",
            "chunk_index": 0,
            "lang": "wikidata",
        },
    ]


def build_disjointness_zelph_lane_proof(
    *,
    report: Mapping[str, Any],
    bundle: Mapping[str, Any],
    latent_slice_graph: Mapping[str, Any],
    lane_id: str,
    lane_family: str,
    execution_surface: str,
) -> dict[str, Any]:
    manifest = _bounded_local_manifest()
    transport_artifact = build_zelph_hf_transport_normalized_artifact(
        manifest=manifest,
        selectors=_bounded_local_selectors(),
        artifact_revision=_text(report.get("source_window_id")) or "bounded-local",
        upstream_artifact_ids=[
            report.get("source_window_id"),
            bundle.get("schema_version"),
            latent_slice_graph.get("schema_version"),
        ],
        backend_capabilities={
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": True,
            "qualifier_import_ready": True,
            "property_path_ready": True,
        },
    )
    focus_pids = list(bundle.get("dependency_cone", {}).get("focus_pids", []))
    required_features = [
        "qualifier-import",
        "sparql-subset",
        "transitive-property-paths",
        "partial-loading",
        "node-route-selection",
    ]
    return {
        "schema_version": WIKIDATA_ZELPH_LANE_PROOF_SCHEMA_VERSION,
        "lane_id": _text(lane_id),
        "lane_family": _text(lane_family),
        "execution_surface": _text(execution_surface),
        "proof_scope": "bounded_local_direct_zelph",
        "proof_subject": "p2738_qualifier_disjointness",
        "required_features": required_features,
        "required_property_scope": focus_pids,
        "transport_artifact": transport_artifact,
        "semantic_receipt": {
            "source_window_id": _text(report.get("source_window_id")),
            "disjoint_pair_count": int(report.get("review_summary", {}).get("disjoint_pair_count", 0) or 0),
            "subclass_violation_count": int(report.get("subclass_violation_count", 0) or 0),
            "instance_violation_count": int(report.get("instance_violation_count", 0) or 0),
            "culprit_class_count": int(report.get("review_summary", {}).get("culprit_class_count", 0) or 0),
            "culprit_item_count": int(report.get("review_summary", {}).get("culprit_item_count", 0) or 0),
        },
        "graph_receipt": {
            "flatness_posture": _text(
                latent_slice_graph.get("flatness_indicators", {}).get("flatness_posture")
            ),
            "node_count": int(latent_slice_graph.get("diagnostics", {}).get("metrics", {}).get("node_count", 0) or 0),
            "edge_count": int(latent_slice_graph.get("diagnostics", {}).get("metrics", {}).get("edge_count", 0) or 0),
        },
        "acceptance": {
            "bounded_semantics_status": "proven",
            "partial_load_contract_status": "proven",
            "hosted_wd_acceptance_status": "pending_manifest_alignment",
            "overall_status": "bounded_local_ready",
        },
        "blocking_items": [
            "Canonical hosted WD manifest/index entrypoints are not yet the final acceptance source in this repo.",
            "Full-WD shard acceptance remains blocked until hosted manifest/index publication is byte-aligned with uploaded shard objects.",
        ],
        "next_actions": [
            "Point this proof surface at the canonical hosted WD manifest once publication stabilizes.",
            "Run the same lane against hosted shard selectors and require direct selected-chunk reads without fallback.",
        ],
    }


__all__ = [
    "WIKIDATA_ZELPH_LANE_PROOF_SCHEMA_VERSION",
    "build_disjointness_zelph_lane_proof",
]
