from __future__ import annotations

from src.runtime.semantic_parity import (
    artifact_identity,
    compare_semantic_surfaces,
    semantic_surface_from_artifacts,
)


def _artifacts() -> dict[str, object]:
    return {
        "annotation_graph": {"graph_ref": "annotation-graph:1"},
        "logical_layer_manifests": [
            {"layer_ref": "layer:base"},
            {"layer_ref": "layer:semantic"},
        ],
        "document_projection_manifest": {"manifest_ref": "projection:1"},
        "typing_hierarchies": {
            "matching": {
                "logical_typing_ref": "logical-typing:1",
                "root_graph_ref": "physical:one",
            }
        },
        "pnf_graph": {
            "representation": "manifest",
            "root_ref": "artifact-root:pnf",
            "ordered_digest": "digest:pnf",
            "record_count": 7,
        },
        "typed_meets": [{"meet_ref": "meet:1"}],
        "stage_build_keys": {"typing": "build:typing"},
    }


def test_artifact_identity_streams_materialised_values() -> None:
    first = artifact_identity([{"value": 1}, {"value": 2}])
    second = artifact_identity([{"value": 1}, {"value": 2}])
    changed = artifact_identity([{"value": 2}, {"value": 1}])

    assert first == second
    assert first["ordered_digest"] != changed["ordered_digest"]


def test_physical_hierarchy_fields_do_not_affect_semantic_surface() -> None:
    first = _artifacts()
    second = _artifacts()
    second["typing_hierarchies"] = {
        "matching": {
            "logical_typing_ref": "logical-typing:1",
            "root_graph_ref": "physical:two",
            "leaf_capacity": 8192,
        }
    }

    first_surface = semantic_surface_from_artifacts(first, document_ref="document:1")
    second_surface = semantic_surface_from_artifacts(second, document_ref="document:1")
    comparison = compare_semantic_surfaces((first_surface, second_surface))

    assert comparison["semantic_parity"] is True
    assert comparison["partition_layout_has_semantic_effect"] is False


def test_semantic_difference_fails_parity() -> None:
    first_surface = semantic_surface_from_artifacts(
        _artifacts(), document_ref="document:1"
    )
    changed = _artifacts()
    changed["annotation_graph"] = {"graph_ref": "annotation-graph:changed"}
    second_surface = semantic_surface_from_artifacts(
        changed, document_ref="document:1"
    )

    comparison = compare_semantic_surfaces((first_surface, second_surface))

    assert comparison["semantic_parity"] is False
    assert comparison["field_parity"]["annotation_graph_ref"] is False
