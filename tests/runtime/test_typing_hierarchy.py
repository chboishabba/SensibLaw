from __future__ import annotations

import pytest

from src.runtime.interval_overlap import IntervalRecord
from src.runtime.typing_hierarchy import (
    TypingCheckpointStop,
    TypingExecutionIdentity,
    execute_partitioned_overlap,
)


def _identity() -> TypingExecutionIdentity:
    return TypingExecutionIdentity(
        document_ref="document:typing-test",
        source_sha256="source-sha",
        parser_contract_ref="parser:test:v1",
        build_key_sha256="build-key",
    )


def _records() -> tuple[tuple[IntervalRecord, ...], tuple[IntervalRecord, ...]]:
    left = tuple(
        IntervalRecord(f"atom-{index}", index * 2, index * 2 + 2)
        for index in range(16)
    )
    right = tuple(
        IntervalRecord(f"mention-{index}", index * 4, index * 4 + 5)
        for index in range(8)
    )
    return left, right


def test_worker_count_does_not_change_typing_identity(tmp_path) -> None:
    left, right = _records()

    serial, serial_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=1,
        leaf_capacity=4,
        checkpoint_root=tmp_path / "serial",
    )
    parallel, parallel_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=4,
        leaf_capacity=4,
        checkpoint_root=tmp_path / "parallel",
    )

    assert parallel == serial
    assert parallel_receipt["logical_typing_ref"] == serial_receipt["logical_typing_ref"]
    assert parallel_receipt["output_digest"] == serial_receipt["output_digest"]
    assert parallel_receipt["root_graph_ref"] == serial_receipt["root_graph_ref"]


def test_partition_size_changes_physical_graph_not_logical_result(tmp_path) -> None:
    left, right = _records()

    small, small_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=4,
        leaf_capacity=4,
        checkpoint_root=tmp_path / "small",
    )
    large, large_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=4,
        leaf_capacity=8,
        checkpoint_root=tmp_path / "large",
    )

    assert large == small
    assert large_receipt["logical_typing_ref"] == small_receipt["logical_typing_ref"]
    assert large_receipt["output_digest"] == small_receipt["output_digest"]
    assert large_receipt["root_graph_ref"] != small_receipt["root_graph_ref"]
    assert large_receipt["semantic_identity_partition_independent"] is True


def test_completed_typing_leaves_are_reused_after_stop(tmp_path) -> None:
    left, right = _records()
    checkpoint_root = tmp_path / "resume"

    with pytest.raises(TypingCheckpointStop):
        execute_partitioned_overlap(
            operation="atom-mention-matching",
            identity=_identity(),
            left_records=left,
            right_records=right,
            workers=1,
            leaf_capacity=4,
            checkpoint_root=checkpoint_root,
            stop_after_new_leaves=1,
        )

    resumed, resumed_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=4,
        leaf_capacity=4,
        checkpoint_root=checkpoint_root,
    )
    fresh, fresh_receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=1,
        leaf_capacity=4,
        checkpoint_root=tmp_path / "fresh",
    )

    assert resumed == fresh
    assert resumed_receipt["logical_typing_ref"] == fresh_receipt["logical_typing_ref"]
    assert resumed_receipt["reused_leaf_count"] >= 1


def test_hierarchy_never_reconstructs_descendant_payloads(tmp_path) -> None:
    left, right = _records()

    _result, receipt = execute_partitioned_overlap(
        operation="atom-mention-matching",
        identity=_identity(),
        left_records=left,
        right_records=right,
        workers=4,
        leaf_capacity=4,
        checkpoint_root=tmp_path,
    )

    assert receipt["descendant_bytes_reconstructed"] == 0
    assert receipt["flattening_free"] is True
    assert all(
        node["descendant_bytes_reconstructed"] == 0 for node in receipt["nodes"]
    )
    assert receipt["complexity"]["planning_right_scan_per_leaf"] is False
