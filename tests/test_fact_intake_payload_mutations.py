from __future__ import annotations

from src.fact_intake.payload_mutations import (
    append_payload_contestation,
    append_payload_observation,
    append_payload_review,
)


def _sample_payload() -> dict[str, object]:
    return {
        "run": {"run_id": "factrun:test"},
        "sources": [{"source_id": "src:1"}],
        "excerpts": [{"excerpt_id": "excerpt:1", "source_id": "src:1"}],
        "statements": [{"statement_id": "statement:1"}],
        "observations": [],
        "fact_candidates": [{"fact_id": "fact:1"}],
        "contestations": [],
        "reviews": [],
    }


def test_append_payload_observation_adds_deterministic_row() -> None:
    payload = _sample_payload()

    append_payload_observation(
        payload,
        statement_index=0,
        predicate_key="actor",
        predicate_family="who",
        object_text="Client",
        object_type="person",
        identity_fields={"fixture_key": "f1", "statement_id": "statement:1", "predicate_key": "actor", "object_text": "Client"},
        provenance={"source": "fixture"},
    )

    row = payload["observations"][0]
    assert row["observation_id"].startswith("obs:")
    assert row["predicate_key"] == "actor"
    assert row["observation_order"] == 1


def test_append_payload_review_and_contestation_add_rows() -> None:
    payload = _sample_payload()

    append_payload_review(
        payload,
        fact_index=0,
        review_status="review_queue",
        reviewer="tester",
        note="note",
        identity_fields={"fixture_key": "f1", "fact_id": "fact:1", "review_status": "review_queue", "note": "note"},
        provenance={"source": "fixture"},
    )
    append_payload_contestation(
        payload,
        fact_index=0,
        statement_index=0,
        status="disputed",
        reason_text="reason",
        author="tester",
        identity_fields={"fixture_key": "f1", "fact_id": "fact:1", "statement_id": "statement:1", "reason_text": "reason"},
        provenance={"source": "fixture"},
    )

    assert payload["reviews"][0]["review_id"].startswith("review:")
    assert payload["contestations"][0]["contestation_id"].startswith("contest:")
