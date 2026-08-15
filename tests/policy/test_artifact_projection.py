from __future__ import annotations

import pytest

from src.policy.artifact_projection import (
    ArtifactProjectionPolicy,
    iter_verified_records,
    materialise_artifact,
    project_artifacts,
)


def test_production_projection_emits_versioned_descriptor_and_bounded_batches() -> None:
    artifacts = {
        "pnf_graph": {
            "graph_ref": "graph:1",
            "factors": [{"factor_ref": f"factor:{index}"} for index in range(5)],
        },
        "phase_boundary": {"completed": True},
    }

    projected, reader = project_artifacts(
        artifacts, policy=ArtifactProjectionPolicy.production()
    )

    descriptor = projected["pnf_graph"]
    assert descriptor["schema_version"] == "sl.artifact_descriptor.v1"
    assert descriptor["representation"] == "manifest"
    assert descriptor["record_count"] == 6
    assert reader is not None
    assert [len(batch) for batch in reader.iter_records("pnf_graph", batch_size=2)] == [
        2,
        2,
        2,
    ]
    first_record = next(iter(reader.iter_records("pnf_graph", batch_size=1)))[0]
    assert first_record["family"] == "factors"
    assert first_record["reconstruction"] == "mapping_repeated_member"
    assert (
        materialise_artifact(projected, "pnf_graph", reader) == artifacts["pnf_graph"]
    )
    assert projected["phase_boundary"] == artifacts["phase_boundary"]


def test_materialised_projection_is_explicit_compatibility_policy() -> None:
    artifacts = {"resolution_demands": [{"demand_ref": "demand:1"}]}
    projected, reader = project_artifacts(
        artifacts,
        policy=ArtifactProjectionPolicy.materialised_compatibility(),
    )
    assert projected == artifacts
    assert reader is None


def test_manifest_materialisation_requires_reader() -> None:
    projected, _reader = project_artifacts(
        {"resolution_demands": []},
        policy=ArtifactProjectionPolicy.production(),
    )
    with pytest.raises(ValueError, match="requires a reader"):
        materialise_artifact(projected, "resolution_demands", None)


def test_reader_replays_a_lazy_source_without_a_second_record_tuple() -> None:
    artifacts = {
        "typed_meets": [{"meet_ref": f"meet:{index}"} for index in range(513)],
    }
    projected, reader = project_artifacts(
        artifacts, policy=ArtifactProjectionPolicy.production()
    )

    assert reader is not None
    assert not hasattr(reader, "_records")
    descriptor = projected["typed_meets"]
    first = [
        row for batch in iter_verified_records(reader, descriptor) for row in batch
    ]
    second = [
        row for batch in iter_verified_records(reader, descriptor) for row in batch
    ]

    assert first == second
    assert len(first) == 513
    assert (
        max(len(batch) for batch in reader.iter_records("typed_meets", batch_size=256))
        == 256
    )
