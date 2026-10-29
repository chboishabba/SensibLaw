import pytest

from src.runtime.relation_delta import (
    CANONICAL_CANDIDATE_RELATION_OWNER_ROUTING,
    RelationDeltaOwnerRouting,
    relation_delta,
)


def test_relation_delta_partitions_key_and_payload_changes() -> None:
    delta = relation_delta(
        current={"same": 1, "replace": 2, "remove": 3},
        desired={"same": 1, "replace": 4, "add": 5},
    )

    assert delta.added == {"add": 5}
    assert delta.removed == {"remove": 3}
    assert delta.replaced == {"replace": (2, 4)}
    assert delta.unchanged == {"same": 1}
    assert delta.desired_count == 3
    assert delta.current_count == 3
    assert delta.physical_row_mutations == 4
    assert delta.unchanged_rows_skipped == 1
    assert delta.changed_key_count == 3
    assert delta.affected_keys == frozenset({"add", "remove", "replace"})
    assert len(delta.affected_keys) == delta.changed_key_count


def test_identical_relation_is_a_zero_write_reconciliation() -> None:
    delta = relation_delta({1: (2, 3)}, {1: (2, 3)})

    assert delta.is_noop
    assert delta.physical_row_mutations == 0
    receipt = delta.receipt(owner_ref="test")
    assert receipt["unchanged_rows_skipped"] == 1
    assert receipt["affected_key_count"] == 0
    assert receipt["unchanged_rows_emit_transitions"] is False



def test_candidate_relation_owner_routing_is_single_and_non_authoritative() -> None:
    routing = CANONICAL_CANDIDATE_RELATION_OWNER_ROUTING

    assert routing.candidate_mutation_owner_count == 1
    assert routing.private_candidate_mutation_bypass_count == 0
    assert routing.hot_path_reconciler_owner_count == 1
    assert routing.reconciliation_receipt_owner_count == 1
    assert routing.receipt(owner_ref="candidate")["semantic_authority_effect"] == "none"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"candidate_mutation_owner_count": 2},
        {"private_candidate_mutation_bypass_count": 1},
        {"hot_path_reconciler_owner_count": 2},
        {"reconciliation_receipt_owner_count": 0},
    ],
)
def test_candidate_relation_owner_routing_fails_closed(
    kwargs: dict[str, int],
) -> None:
    values = {
        "candidate_mutation_owner_count": 1,
        "private_candidate_mutation_bypass_count": 0,
        "hot_path_reconciler_owner_count": 1,
        "reconciliation_receipt_owner_count": 1,
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        RelationDeltaOwnerRouting(**values)
