from __future__ import annotations

from types import SimpleNamespace

from src.storage.postgres.manifest_metadata_hot_path import (
    execution_scalar_metadata,
    install_descriptor_metadata_hot_path,
)


def test_primitive_mapping_metadata_is_read_without_record_replay() -> None:
    reader = SimpleNamespace(
        _sources={
            "pnf_graph": {
                "graph_ref": "graph:1",
                "closure_state": "closed",
                "factors": ({"factor_ref": "factor:1"},),
            }
        }
    )

    assert execution_scalar_metadata(reader, {"artifact_key": "pnf_graph"}) == {
        "graph_ref": "graph:1",
        "closure_state": "closed",
    }


def test_rich_mapping_scalar_fails_closed_to_preflight() -> None:
    reader = SimpleNamespace(
        _sources={
            "annotation_layer": {
                "layer_ref": "layer:1",
                "text_sha256": "00" * 32,
                "metadata": {"producer": "rich-scalar"},
                "token_annotations": (),
            }
        }
    )

    assert execution_scalar_metadata(reader, {"artifact_key": "annotation_layer"}) is None


def test_descriptor_installer_falls_back_when_direct_graph_metadata_is_unsafe() -> None:
    calls: list[str] = []

    class Compiler:
        @staticmethod
        def _descriptor_metadata(_reader, _descriptor):
            calls.append("fallback")
            return {"graph_ref": "graph:fallback"}

    compiler = Compiler()
    original = install_descriptor_metadata_hot_path(compiler)
    reader = SimpleNamespace(
        _sources={
            "pnf_graph": {
                "graph_ref": "graph:direct",
                "rich_scalar": {"x": 1},
                "factors": (),
            }
        }
    )

    assert compiler._descriptor_metadata(reader, {"artifact_key": "pnf_graph"}) == {
        "graph_ref": "graph:fallback"
    }
    assert calls == ["fallback"]
    assert original is not compiler._descriptor_metadata
