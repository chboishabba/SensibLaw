from __future__ import annotations

from src.fact_intake.projection_helpers import (
    build_relation_observation,
    build_role_observation,
    fact_status_for_statement,
    observation_status_from_relation,
)


def test_observation_status_from_relation_maps_promotion_states() -> None:
    assert observation_status_from_relation({"promotion_status": "promoted"}) == "captured"
    assert observation_status_from_relation({"promotion_status": "abstained"}) == "abstained"
    assert observation_status_from_relation({"promotion_status": "candidate"}) == "uncertain"


def test_fact_status_for_statement_rolls_up_observation_statuses() -> None:
    assert fact_status_for_statement([{"observation_status": "captured"}]) == "candidate"
    assert fact_status_for_statement([{"observation_status": "abstained"}]) == "abstained"
    assert fact_status_for_statement([]) == "no_fact"


def test_build_role_observation_shapes_shared_projection_row() -> None:
    row = build_role_observation(
        run_id="factrun:1",
        event_id="e1",
        statement_id="statement:1",
        excerpt_id="excerpt:1",
        source_id="src:1",
        observation_order=1,
        role_index=1,
        predicate_key="actor",
        predicate_family="actor_identification",
        object_text="Alice",
        object_type="semantic_entity",
        object_ref="entity:alice",
        subject_text=None,
        observation_status="captured",
        semantic_run_id="semantic:1",
        role_kind="speaker",
    )
    assert row["predicate_key"] == "actor"
    assert row["predicate_family"] == "actor_identification"
    assert row["provenance"]["role_kind"] == "speaker"


def test_build_relation_observation_shapes_shared_projection_row() -> None:
    row = build_relation_observation(
        run_id="factrun:1",
        event_id="e1",
        kind="relation",
        statement_id="statement:1",
        excerpt_id="excerpt:1",
        source_id="src:1",
        observation_order=1,
        relation_index=2,
        predicate_key="acted_on",
        predicate_family="object_target",
        object_text="Clinic letter",
        object_type="semantic_entity",
        object_ref="entity:letter",
        subject_text="Alice",
        observation_status="uncertain",
        semantic_run_id="semantic:1",
        relation_candidate_id="cand:1",
        source_predicate_key="replied_to",
        promotion_status="candidate",
    )
    assert row["predicate_key"] == "acted_on"
    assert row["subject_text"] == "Alice"
    assert row["provenance"]["source_predicate_key"] == "replied_to"
