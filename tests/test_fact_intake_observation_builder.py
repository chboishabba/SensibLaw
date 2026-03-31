from __future__ import annotations

from src.fact_intake.observation_builder import build_observation_id, build_observation_row


def test_build_observation_id_is_deterministic() -> None:
    observation_id = build_observation_id(
        run_id="factrun:1",
        event_id="e1",
        kind="role",
        identity_fields={"index": 1, "predicate_key": "actor", "object_text": "Alice"},
    )
    assert observation_id.startswith("obs:")
    assert observation_id == build_observation_id(
        run_id="factrun:1",
        event_id="e1",
        kind="role",
        identity_fields={"index": 1, "predicate_key": "actor", "object_text": "Alice"},
    )


def test_build_observation_row_shapes_shared_fields() -> None:
    row = build_observation_row(
        observation_id="obs:1",
        statement_id="statement:1",
        excerpt_id="excerpt:1",
        source_id="src:1",
        observation_order=1,
        predicate_key="actor",
        predicate_family="actor_identification",
        object_text="Alice",
        object_type="semantic_entity",
        object_ref="entity:alice",
        subject_text=None,
        observation_status="captured",
        provenance={"semantic_run_id": "semantic:1"},
    )
    assert row["predicate_key"] == "actor"
    assert row["predicate_family"] == "actor_identification"
    assert row["object_ref"] == "entity:alice"
    assert row["provenance"]["semantic_run_id"] == "semantic:1"
