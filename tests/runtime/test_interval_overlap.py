from __future__ import annotations

import pytest

from src.runtime.interval_overlap import IntervalRecord, TokenIntervalIndex


def _naive(
    records: tuple[IntervalRecord, ...], start: int, end: int
) -> tuple[str, ...]:
    return tuple(
        sorted(row.ref for row in records if start < row.end and end > row.start)
    )


def test_interval_index_matches_naive_overlap() -> None:
    records = (
        IntervalRecord("a", 0, 4),
        IntervalRecord("b", 3, 8),
        IntervalRecord("c", 8, 10),
        IntervalRecord("d", 9, 16),
        IntervalRecord("e", 30, 40),
    )
    index = TokenIntervalIndex(records)

    for start, end in ((0, 1), (2, 5), (4, 8), (8, 9), (9, 12), (20, 31)):
        assert index.overlapping(start, end) == _naive(records, start, end)


def test_localized_query_does_not_scan_the_full_collection() -> None:
    records = tuple(
        IntervalRecord(f"r-{index}", index * 3, index * 3 + 1) for index in range(4096)
    )
    index = TokenIntervalIndex(records)

    matches, receipt = index.overlapping_with_receipt(6144, 6145)

    assert matches == ("r-2048",)
    assert receipt.match_count == 1
    assert receipt.node_visits < 32
    assert receipt.candidate_checks < 64
    assert receipt.work_units < 96


def test_interval_index_rejects_invalid_queries() -> None:
    index = TokenIntervalIndex((IntervalRecord("a", 0, 1),))

    with pytest.raises(ValueError):
        index.overlapping(1, 1)
