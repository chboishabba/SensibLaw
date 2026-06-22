from __future__ import annotations

import json

from src.policy.suite_normalized_artifact import (
    build_zelph_shard_transport_normalized_artifact,
)


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
            },
            {
                "selector_kind": "section",
                "selector_id": "sel:2",
                "sink_uris": ["hf://datasets/zelph/other"],
                "transport_object_uri": "hf://objects/zelph/section-object",
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

    assert artifact["authority"]["promotion_receipt_ref"] is None
    assert "zelph:artifact:1" not in artifact["lineage"]["upstream_artifact_ids"]
    assert "sink_uri" not in json.dumps(artifact)
    assert "sink_uris" not in json.dumps(artifact)
    assert "object_uri" not in json.dumps(artifact)
    assert "object_uris" not in json.dumps(artifact)
