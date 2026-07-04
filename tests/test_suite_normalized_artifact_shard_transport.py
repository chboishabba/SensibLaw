from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.policy.suite_normalized_artifact import (
    build_zelph_hf_transport_normalized_artifact,
    build_zelph_shard_transport_normalized_artifact,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_manifest_builder_module():
    module_path = ROOT / "tools" / "build_zelph_hf_manifest.py"
    spec = importlib.util.spec_from_file_location("build_zelph_hf_manifest", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_zelph_shard_transport_normalized_artifact_is_candidate_only_and_partial_load_aware() -> None:
    artifact = build_zelph_shard_transport_normalized_artifact(
        artifact_id="zelph:artifact:1",
        artifact_revision="rev-2026-06-22",
        artifact_class="shared_shard_transport",
        selectors=[
            {
                "selector_kind": "metadata",
                "selector_id": "sel:1",
                "sink_uri": "hf://datasets/zelph/private",
                "object_uri": "hf://objects/zelph/private-object",
                "criteria": {"kind": "shared-shard"},
                "raw_text": "should not surface",
                "full_receipts": [{"receipt_id": "r:1"}],
                "spans": [{"start": 1, "end": 2}],
                "support_count": 2,
                "contradiction_count": 1,
            },
            {
                "selector_kind": "section",
                "selector_id": "sel:2",
                "sink_uris": ["hf://datasets/zelph/other"],
                "transport_object_uri": "hf://objects/zelph/section-object",
                "criteria": {"kind": "section", "span": {"start": 3, "end": 4}},
                "diagnostics": {"trace": "noisy"},
            },
        ],
        selected_shard_ids=["shard:1", "shard:2", "shard:1"],
        selected_sections=["intro", "methods", "intro"],
        upstream_artifact_ids=["upstream:root", "upstream:delta"],
        build_provenance={
            "build_id": "build:42",
            "source_run_id": "run:9",
            "sink_uri": "hf://datasets/zelph/sink",
            "object_uri": "hf://objects/zelph/sink-object",
            "raw_text": "should not surface",
            "diagnostics": {"trace": "noisy"},
        },
    )

    assert artifact["schema_version"] == "itir.normalized.artifact.v1"
    assert artifact["artifact_role"] == "transport_view"
    assert artifact["canonical_identity"] == {
        "identity_class": "zelph_shard_transport",
        "identity_key": "shared_shard_transport:zelph:artifact:1:rev-2026-06-22",
        "aliases": ["zelph:artifact:1", "rev-2026-06-22", "shared_shard_transport"],
    }
    assert artifact["provenance_anchor"] == {
        "source_system": "Zelph-HF",
        "source_artifact_id": "zelph:artifact:1",
        "anchor_kind": "zelph_shard_transport",
        "anchor_ref": "semantic_context.suite_normalized_artifact",
    }
    assert artifact["context_envelope_ref"] == {
        "envelope_id": "zelph:artifact:1",
        "envelope_kind": "zelph_shard_transport",
    }

    authority = artifact["authority"]
    assert authority == {
        "authority_class": "transport_view",
        "candidate": True,
        "derived": True,
        "transport_only": True,
        "promotion_receipt_ref": None,
    }
    assert "truth" not in authority
    assert "support" not in authority
    assert "admissibility" not in authority
    assert "promotion_authority" not in authority

    assert artifact["non_authority_flags"] == {
        "truth_authority": False,
        "promotion_authority": False,
        "transport_authority": False,
    }

    assert artifact["invariants"] == {
        "partial_view": True,
        "subset_of_artifact": True,
        "complete_closure": False,
        "truth_authority": False,
        "promotion_authority": False,
    }
    assert artifact["lineage"] == {
        "upstream_artifact_ids": ["upstream:root", "upstream:delta"],
        "build_provenance": {
            "build_id": "build:42",
            "source_run_id": "run:9",
        },
        "artifact_revision": "rev-2026-06-22",
        "artifact_class": "shared_shard_transport",
    }
    assert artifact["selectors"] == [
        {
            "selector_kind": "metadata",
            "selector_id": "sel:1",
            "criteria": {"kind": "shared-shard"},
        },
        {
            "selector_kind": "section",
            "selector_id": "sel:2",
            "criteria": {"kind": "section"},
        },
    ]
    assert artifact["route_selectors"] == artifact["selectors"]
    assert artifact["selected_shard_ids"] == ["shard:1", "shard:2", "shard:1"]
    assert artifact["selected_sections"] == ["intro", "methods", "intro"]
    assert artifact["summary"] == {
        "artifact_class": "shared_shard_transport",
        "artifact_revision": "rev-2026-06-22",
        "source_system": "Zelph-HF",
        "partial_view": True,
        "partial_load": True,
        "candidate_only": True,
        "selector_count": 2,
        "route_selector_count": 2,
        "selected_shard_count": 3,
        "selected_section_count": 3,
    }

    projection = artifact["review_packet_projection"]
    assert projection == {
        "authority_label": "transport_view",
        "authority_boundary": {
            "authority_class": "transport_view",
            "candidate_only": True,
            "derived": True,
            "partial_view": True,
            "transport_only": True,
            "complete_closure": False,
            "excludes": [
                "raw_text",
                "full_receipts",
                "spans",
                "sink/object_uris",
                "bulky_diagnostics",
            ],
        },
        "candidate_facts": [
            {"fact_kind": "selected_shard", "fact_ref": "shard:1"},
            {"fact_kind": "selected_shard", "fact_ref": "shard:2"},
            {"fact_kind": "selected_shard", "fact_ref": "shard:1"},
            {"fact_kind": "selected_section", "fact_ref": "intro"},
            {"fact_kind": "selected_section", "fact_ref": "methods"},
            {"fact_kind": "selected_section", "fact_ref": "intro"},
        ],
        "candidate_refs": ["sel:1", "sel:2"],
        "route_selectors": [
            {
                "selector_kind": "metadata",
                "selector_id": "sel:1",
                "criteria": {"kind": "shared-shard"},
                "support_count": 2,
                "contradiction_count": 1,
            },
            {
                "selector_kind": "section",
                "selector_id": "sel:2",
                "criteria": {"kind": "section"},
            },
        ],
        "citations": ["sel:1", "sel:2"],
        "provenance_refs": [
            "upstream:root",
            "upstream:delta",
            "zelph:artifact:1",
            "rev-2026-06-22",
            "build:42",
            "run:9",
            "semantic_context.suite_normalized_artifact",
        ],
        "support_count": 2,
        "contradiction_count": 1,
        "artifact_ref": "zelph:artifact:1",
        "artifact_revision": "rev-2026-06-22",
        "artifact_class": "shared_shard_transport",
        "source_system": "Zelph-HF",
    }

    assert artifact["authority"]["promotion_receipt_ref"] is None
    assert "zelph:artifact:1" not in artifact["lineage"]["upstream_artifact_ids"]
    artifact_json = json.dumps(artifact)
    assert "hf://datasets/zelph/private" not in artifact_json
    assert "hf://objects/zelph/private-object" not in artifact_json
    assert "hf://datasets/zelph/other" not in artifact_json
    assert "hf://objects/zelph/section-object" not in artifact_json
    assert "hf://datasets/zelph/sink" not in artifact_json
    assert "hf://objects/zelph/sink-object" not in artifact_json
    assert "should not surface" not in artifact_json
    assert "noisy" not in artifact_json
    assert "r:1" not in artifact_json
    assert all(
        "span" not in selector.get("criteria", {})
        for selector in artifact["review_packet_projection"]["route_selectors"]
    )
    assert all(
        "raw_text" not in selector and "full_receipts" not in selector and "diagnostics" not in selector
        for selector in artifact["review_packet_projection"]["route_selectors"]
    )


def test_build_zelph_hf_transport_normalized_artifact_summarizes_itir_manifest_contract() -> None:
    artifact = build_zelph_hf_transport_normalized_artifact(
        manifest={
            "manifestVersion": "zelph-hf-layout/v2",
            "createdAtUtc": "2026-07-02T00:00:00Z",
            "storageMode": "multi-object-shards",
            "transport": {
                "primary": "hf-object-fetch",
                "fallback": "local-file",
            },
            "source": {
                "binPath": "/tmp/wikidata-20260309-all.bin",
                "headerLengthBytes": 8192,
                "totalChunkCount": 12,
                "totalChunkBytes": 4096,
            },
            "selectorModel": {
                "unit": "section-chunk",
                "supportedSections": ["left", "right", "nameOfNode", "nodeOfName"],
                "supportedOperations": ["header-probe", "selected-chunk-read", "node-route"],
                "unsupportedOperations": ["fullReasoningSafe"],
            },
            "capabilities": {
                "headerProbe": True,
                "selectedChunkRead": True,
                "nodeRouteIndex": True,
            },
            "hfObjects": {
                "manifest": {
                    "path": "hf://datasets/acrion/zelph/wikidata-20260309-all/wikidata-20260309-all.hf-v2.json",
                },
            },
            "sections": {
                "left": {"chunkCount": 4},
                "right": {"chunkCount": 4},
                "nameOfNode": {"chunkCount": 2},
                "nodeOfName": {"chunkCount": 2},
            },
        },
        selectors=[
            {
                "selector_kind": "route",
                "selector_id": "sel:route",
                "section": "left",
                "chunk_indices": [0, 1],
                "route_name": "Q42",
                "route_lang": "wikidata",
                "object_uri": "hf://datasets/acrion/zelph/private",
            },
            {
                "selector_kind": "section",
                "selector_id": "sel:section",
                "section": "nameOfNode",
                "chunk_index": 3,
                "raw_text": "nope",
            },
        ],
        upstream_artifact_ids=["wikidata-20260309-all.bin"],
        backend_capabilities={
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": True,
            "transport_object_uri": "hf://datasets/acrion/zelph/object",
        },
    )

    assert artifact["artifact_id"] == "wikidata-20260309-all.hf-v2.json"
    assert artifact["summary"]["manifest_version"] == "zelph-hf-layout/v2"
    assert artifact["summary"]["transport_primary"] == "hf-object-fetch"
    assert artifact["summary"]["node_route_index"] is True
    assert artifact["summary"]["selected_chunk_read"] is True
    assert artifact["summary"]["predicate_index_persistence"] is True
    assert artifact["selected_shard_ids"] == ["left:0", "left:1", "nameOfNode:3"]
    assert artifact["selected_sections"] == ["left", "nameOfNode"]
    assert artifact["lineage"]["build_provenance"] == {
        "manifest_version": "zelph-hf-layout/v2",
        "storage_mode": "multi-object-shards",
        "transport_primary": "hf-object-fetch",
        "transport_fallback": "local-file",
        "selector_unit": "section-chunk",
        "supported_sections": ["left", "right", "nameOfNode", "nodeOfName"],
        "supported_operations": ["header-probe", "selected-chunk-read", "node-route"],
        "unsupported_operations": ["fullReasoningSafe"],
        "node_route_index": True,
        "header_probe": True,
        "selected_chunk_read": True,
        "source_header_length_bytes": 8192,
        "source_total_chunk_count": 12,
        "source_total_chunk_bytes": 4096,
        "section_chunk_counts": {
            "left": 4,
            "right": 4,
            "nameOfNode": 2,
            "nodeOfName": 2,
        },
        "backend_capabilities": {
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": True,
        },
    }
    assert artifact["review_packet_projection"]["transport_capabilities"] == {
        "manifest_version": "zelph-hf-layout/v2",
        "transport_primary": "hf-object-fetch",
        "node_route_index": True,
        "selected_chunk_read": True,
        "supported_operations": ["header-probe", "selected-chunk-read", "node-route"],
        "supported_sections": ["left", "right", "nameOfNode", "nodeOfName"],
        "backend_capabilities": {
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": True,
        },
    }
    artifact_json = json.dumps(artifact)
    assert "hf://datasets/acrion/zelph/private" not in artifact_json
    assert "hf://datasets/acrion/zelph/object" not in artifact_json
    assert '"raw_text": "nope"' not in artifact_json


def test_build_zelph_hf_transport_normalized_artifact_accepts_manifest_builder_output(tmp_path: Path) -> None:
    builder = _load_manifest_builder_module()
    bin_path = tmp_path / "sample.bin"
    index_path = tmp_path / "sample.index.json"
    output_path = tmp_path / "sample.hf-v2.json"
    route_path = tmp_path / "sample.route.json"

    bin_path.write_bytes(b"0" * 80)
    route_path.write_text('{"routeVersion":"zelph-node-route/v1"}\n', encoding="utf-8")
    index_path.write_text(
        json.dumps(
            {
                "header": {"offset": 0, "length": 8},
                "left": [{"chunkIndex": 0, "offset": 8, "length": 10, "which": "left"}],
                "right": [{"chunkIndex": 0, "offset": 18, "length": 10, "which": "right"}],
                "nameOfNode": [
                    {"chunkIndex": 0, "offset": 28, "length": 10, "lang": "wikidata"},
                    {"chunkIndex": 1, "offset": 38, "length": 10, "lang": "en"},
                ],
                "nodeOfName": [
                    {"chunkIndex": 0, "offset": 48, "length": 10, "lang": "wikidata"},
                    {"chunkIndex": 1, "offset": 58, "length": 10, "lang": "en"},
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest, _sections = builder.build_manifest(
        bin_path,
        index_path,
        output_path,
        "hf://datasets/acrion/zelph",
        "sample",
        "v2",
        node_route_path=route_path,
    )
    artifact = build_zelph_hf_transport_normalized_artifact(
        manifest=manifest,
        selectors=[
            {
                "selector_kind": "section",
                "selector_id": "sel:left0",
                "section": "left",
                "chunk_index": 0,
                "object_uri": "hf://datasets/acrion/zelph/sample/shards/left/chunk-000000.capnp-packed",
            },
            {
                "selector_kind": "section",
                "selector_id": "sel:name1",
                "section": "nameOfNode",
                "chunk_index": 1,
                "lang": "en",
            },
        ],
        upstream_artifact_ids=["sample.bin"],
        backend_capabilities={
            "predicate_index_persistence": True,
            "sparql_partial_loading_ready": False,
            "transport_object_uri": "hf://datasets/acrion/zelph/private",
        },
    )

    assert artifact["summary"]["manifest_version"] == "zelph-hf-layout/v2"
    assert artifact["summary"]["storage_mode"] == "multi-object-shards"
    assert artifact["summary"]["transport_primary"] == "hf-object-fetch"
    assert artifact["summary"]["node_route_index"] is True
    assert artifact["selected_shard_ids"] == ["left:0", "nameOfNode:1"]
    assert artifact["selected_sections"] == ["left", "nameOfNode"]
    assert artifact["lineage"]["build_provenance"]["section_chunk_counts"] == {
        "left": 1,
        "right": 1,
        "nameOfNode": 2,
        "nodeOfName": 2,
    }
    assert artifact["review_packet_projection"]["transport_capabilities"]["supported_sections"] == [
        "left",
        "right",
        "nameOfNode",
        "nodeOfName",
    ]
    artifact_json = json.dumps(artifact)
    assert "hf://datasets/acrion/zelph/sample/shards" not in artifact_json
    assert "hf://datasets/acrion/zelph/private" not in artifact_json


def test_build_zelph_hf_transport_normalized_artifact_requires_manifest_version() -> None:
    try:
        build_zelph_hf_transport_normalized_artifact(manifest={}, selectors=[])
    except ValueError as exc:
        assert "manifestVersion" in str(exc)
    else:
        raise AssertionError("expected ValueError")
