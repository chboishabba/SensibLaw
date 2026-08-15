from __future__ import annotations

from typing import Any

from src.policy import artifact_projection
from src.policy.carrier_orchestration_hot_path import _seal_projected_reader
from src.storage.postgres.sealed_manifest_family import direct_sealed_descriptor_family


def test_sealed_mapping_family_reads_source_without_record_envelopes(monkeypatch) -> None:
    source = {
        "graph_ref": "graph:1",
        "factors": tuple(
            {"factor_ref": f"factor:{index}", "factor_type": "norm"}
            for index in range(5)
        ),
    }
    projector = _seal_projected_reader(artifact_projection.project_artifacts)
    projected, reader = projector(
        {"pnf_graph": source},
        policy=artifact_projection.ArtifactProjectionPolicy.production(),
    )
    assert reader is not None
    descriptor = projected["pnf_graph"]

    def forbidden(*_args: Any, **_kwargs: Any):
        raise AssertionError("direct sealed family must not reconstruct manifest envelopes")

    monkeypatch.setattr(reader, "iter_records", forbidden)
    direct = direct_sealed_descriptor_family(
        reader,
        descriptor,
        "factors",
        batch_size=2,
    )
    assert direct is not None
    rows = [row for batch in direct for row in batch]

    assert rows == list(source["factors"])


def test_sealed_sequence_rows_preserve_order() -> None:
    source = tuple({"demand_ref": f"demand:{index}"} for index in range(5))
    projector = _seal_projected_reader(artifact_projection.project_artifacts)
    projected, reader = projector(
        {"resolution_demands": source},
        policy=artifact_projection.ArtifactProjectionPolicy.production(),
    )
    assert reader is not None
    direct = direct_sealed_descriptor_family(
        reader,
        projected["resolution_demands"],
        "rows",
        batch_size=2,
    )
    assert direct is not None

    assert [row for batch in direct for row in batch] == list(source)


def test_unsealed_reader_requires_canonical_fallback() -> None:
    source = ({"demand_ref": "demand:1"},)
    projected, reader = artifact_projection.project_artifacts(
        {"resolution_demands": source},
        policy=artifact_projection.ArtifactProjectionPolicy.production(),
    )
    assert reader is not None

    assert (
        direct_sealed_descriptor_family(
            reader,
            projected["resolution_demands"],
            "rows",
        )
        is None
    )
