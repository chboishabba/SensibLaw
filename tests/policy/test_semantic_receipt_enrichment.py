from __future__ import annotations

import json

from src.policy.semantic_receipt_enrichment import enrich_semantic_receipt
from src.runtime.semantic_parity import semantic_surface_from_execution_receipt


def test_completed_artifacts_enrich_stage_identity_receipt(tmp_path) -> None:
    path = tmp_path / "semantic-execution-receipt.json"
    path.write_text(
        json.dumps(
            {
                "state": "completed",
                "document_ref": "document:1",
                "typing_hierarchies": {},
                "amplification": {
                    "identity_receipt": {
                        "annotation_graph_ref": "annotation-graph:1",
                        "logical_layer_refs": ["layer:1"],
                        "manifest_descriptors": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    receipt = enrich_semantic_receipt(
        path,
        artifacts={
            "build_key_sha256": "operational-key",
            "stage_build_keys": {"typing": "stage-build:typing"},
            "semantic_reduction_refs": ["reduction:2", "reduction:1"],
            "constraint_assessments": [
                {"assessment_ref": "assessment:2"},
                {"assessment_ref": "assessment:1"},
            ],
        },
    )

    identity = receipt["amplification"]["identity_receipt"]
    assert identity["stage_build_keys"] == {"typing": "stage-build:typing"}
    assert identity["operational_build_key_sha256"] == "operational-key"
    assert identity["semantic_reduction_refs"] == ["reduction:1", "reduction:2"]
    assert identity["constraint_assessment_refs"] == [
        "assessment:1",
        "assessment:2",
    ]
    assert receipt["identity_enrichment"]["state"] == "complete"
    assert semantic_surface_from_execution_receipt(receipt)["stage_build_keys"] == {
        "typing": "stage-build:typing"
    }


def test_reference_surface_binds_logical_typing_refs(tmp_path) -> None:
    path = tmp_path / "semantic-execution-receipt.json"
    path.write_text(
        json.dumps(
            {
                "state": "completed",
                "document_ref": "document:1",
                "typing_hierarchies": {
                    "local_type_carrier_build": {
                        "logical_typing_ref": "logical-typing:carrier"
                    }
                },
                "amplification": {"identity_receipt": {}},
            }
        ),
        encoding="utf-8",
    )
    descriptor = {
        "schema_version": "sensiblaw.streaming-family-descriptor.v1",
        "family": "factors",
        "storage_kind": "jsonl",
        "record_count": 1,
        "byte_count": 12,
        "ordered_digest": "digest:factors",
        "encoding_ref": "canonical-jsonl:v1",
        "path": "/tmp/factors.jsonl",
    }

    receipt = enrich_semantic_receipt(
        path,
        artifacts={
            "streaming_semantic_build": {
                "reference_backed": True,
                "document_ref": "document:1",
                "revision": 1,
                "reference_finalization_contract": ("reference-backed-finalization:v1"),
                "owner_fingerprint": {},
                "materialized_reduction": {"graph_ref": "graph:1"},
                "fixed_point_certificate": {
                    "certificate_ref": "certificate:1",
                    "ledger_ref": "ledger:1",
                    "materialized_graph_ref": "graph:1",
                    "local_fixed_point": "reached",
                },
                "family_manifests": {"factors": descriptor},
            }
        },
    )

    surface = receipt["amplification"]["identity_receipt"]["reference_semantic_surface"]
    assert surface["logical_typing_refs"] == {
        "local_type_carrier_build": "logical-typing:carrier"
    }
    assert receipt["reference_backed_execution"]["logical_typing_refs"] == {
        "local_type_carrier_build": "logical-typing:carrier"
    }


def test_identity_enrichment_never_adds_physical_partition_fields(tmp_path) -> None:
    path = tmp_path / "semantic-execution-receipt.json"
    path.write_text(
        json.dumps(
            {
                "state": "completed",
                "document_ref": "document:1",
                "typing_hierarchies": {},
                "amplification": {"identity_receipt": {}},
            }
        ),
        encoding="utf-8",
    )

    receipt = enrich_semantic_receipt(
        path,
        artifacts={
            "stage_build_keys": {},
            "semantic_runtime_configuration": {
                "closure_workers": 4,
                "owner_partitions": 8,
            },
        },
    )

    identity = receipt["amplification"]["identity_receipt"]
    assert "semantic_runtime_configuration" not in identity
    assert "closure_workers" not in identity
    assert "owner_partitions" not in identity
    assert receipt["identity_enrichment"]["physical_partition_fields_included"] is False
