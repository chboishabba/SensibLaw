from __future__ import annotations

import pytest

from src.runtime.streaming_partition_refinement import (
    partition_geometry,
    target_chars_for_partition_count,
)


def test_target_chars_for_partition_count_is_bounded_and_ceil_divides() -> None:
    assert target_chars_for_partition_count(
        source_chars=100_000,
        target_partitions=10,
    ) == 10_000
    assert target_chars_for_partition_count(
        source_chars=10_001,
        target_partitions=10,
    ) == 1_024
    assert target_chars_for_partition_count(
        source_chars=32_769,
        target_partitions=4,
    ) == 8_193


def test_partition_geometry_accounts_for_context_duplication_and_skew() -> None:
    receipt = partition_geometry(
        (
            (0, 100, 0, 110),
            (100, 200, 90, 210),
            (200, 250, 190, 250),
        )
    )

    assert receipt.partition_count == 3
    assert receipt.source_owner_chars == 250
    assert receipt.total_context_chars == 290
    assert receipt.duplicated_context_chars == 40
    assert receipt.context_duplication_fraction == pytest.approx(0.16)
    assert receipt.smallest_owner_chars == 50
    assert receipt.largest_owner_chars == 100
    assert receipt.owner_skew_ratio == pytest.approx(2.0)


def test_partition_geometry_rejects_invalid_physical_intervals() -> None:
    with pytest.raises(ValueError, match="at least one"):
        partition_geometry(())
    with pytest.raises(ValueError, match="non-empty"):
        partition_geometry(((4, 4, 4, 4),))
    with pytest.raises(ValueError, match="contain"):
        partition_geometry(((0, 10, 2, 8),))
