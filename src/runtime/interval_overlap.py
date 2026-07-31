"""Immutable output-sensitive token interval indexes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True, order=True)
class IntervalRecord:
    ref: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.ref:
            raise ValueError("interval reference is required")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("interval coordinates must form a non-empty half-open range")


@dataclass(frozen=True)
class _IntervalNode:
    center: int
    crossing_by_start: tuple[IntervalRecord, ...]
    crossing_by_end: tuple[IntervalRecord, ...]
    left: "_IntervalNode | None" = None
    right: "_IntervalNode | None" = None


class TokenIntervalIndex:
    """Read-only interval tree with O(log n + k) overlap queries."""

    def __init__(self, records: Iterable[IntervalRecord]):
        rows = tuple(sorted(set(records), key=lambda row: (row.start, row.end, row.ref)))
        self.records = rows
        self._root = self._build(rows)

    @classmethod
    def _build(cls, rows: Sequence[IntervalRecord]) -> _IntervalNode | None:
        if not rows:
            return None
        midpoints = sorted((row.start + row.end) // 2 for row in rows)
        center = midpoints[len(midpoints) // 2]
        left: list[IntervalRecord] = []
        right: list[IntervalRecord] = []
        crossing: list[IntervalRecord] = []
        for row in rows:
            if row.end <= center:
                left.append(row)
            elif row.start > center:
                right.append(row)
            else:
                crossing.append(row)
        if not crossing:
            pivot = rows[len(rows) // 2]
            crossing.append(pivot)
            left = [row for row in rows if row != pivot and row.end <= center]
            right = [row for row in rows if row != pivot and row.start > center]
        return _IntervalNode(
            center=center,
            crossing_by_start=tuple(
                sorted(crossing, key=lambda row: (row.start, row.end, row.ref))
            ),
            crossing_by_end=tuple(
                sorted(crossing, key=lambda row: (-row.end, row.start, row.ref))
            ),
            left=cls._build(tuple(left)),
            right=cls._build(tuple(right)),
        )

    def overlapping(self, start: int, end: int) -> tuple[str, ...]:
        if start < 0 or end <= start:
            raise ValueError("query coordinates must form a non-empty half-open range")
        matches: set[str] = set()

        def visit(node: _IntervalNode | None) -> None:
            if node is None:
                return
            if end <= node.center:
                for row in node.crossing_by_start:
                    if row.start >= end:
                        break
                    matches.add(row.ref)
                visit(node.left)
                return
            if start > node.center:
                for row in node.crossing_by_end:
                    if row.end <= start:
                        break
                    matches.add(row.ref)
                visit(node.right)
                return
            matches.update(row.ref for row in node.crossing_by_start)
            visit(node.left)
            visit(node.right)

        visit(self._root)
        return tuple(sorted(matches))


__all__ = ["IntervalRecord", "TokenIntervalIndex"]
