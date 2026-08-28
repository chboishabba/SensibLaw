from src.runtime.relation_delta import relation_delta


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


def test_identical_relation_is_a_zero_write_reconciliation() -> None:
    delta = relation_delta({1: (2, 3)}, {1: (2, 3)})

    assert delta.is_noop
    assert delta.physical_row_mutations == 0
    receipt = delta.receipt(owner_ref="test")
    assert receipt["unchanged_rows_skipped"] == 1
    assert receipt["unchanged_rows_emit_transitions"] is False
