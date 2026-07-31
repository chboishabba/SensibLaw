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
class OverlapQueryReceipt:
    start: int
    end: int
    match_count: int
    node_visits: int
    candidate_checks: int

    @property
    def work_units(self) -> int:
        return self.node_visits + self.candidate_checks


@dataclass(frozen=True)
class _IntervalNode:
    """One start-ordered interval node with a left-subtree pruning bound."""

    record: IntervalRecord
    max_end: int
    left: "_IntervalNode | None" = None
    right: "_IntervalNode | None" = None


class TokenIntervalIndex:
    """Read-only balanced interval tree with output-sensitive overlap queries.

    Nodes are ordered by interval start. ``max_end`` stores the greatest end
    coordinate in each subtree, allowing a query to skip every left subtree
    that cannot extend past the query start. The start ordering independently
    prevents descent into right subtrees whose records all begin at or beyond
    the query end.
    """

    def __init__(self, records: Iterable[IntervalRecord]):
        rows = tuple(sorted(set(records), key=lambda row: (row.start, row.end, row.ref)))
        self.records = rows
        self._root = self._build(rows)

    @classmethod
    def _build(cls, rows: Sequence[IntervalRecord]) -> _IntervalNode | None:
        if not rows:
            return None
        midpoint = len(rows) // 2
        record = rows[midpoint]
        left = cls._build(rows[:midpoint])
        right = cls._build(rows[midpoint + 1 :])
        max_end = max(
            record.end,
            left.max_end if left is not None else record.end,
            right.max_end if right is not None else record.end,
        )
        return _IntervalNode(
            record=record,
            max_end=max_end,
            left=left,
            right=right,
        )

    def overlapping_with_receipt(
        self, start: int, end: int
    ) -> tuple[tuple[str, ...], OverlapQueryReceipt]:
        if start < 0 or end <= start:
            raise ValueError("query coordinates must form a non-empty half-open range")
        matches: list[str] = []
        node_visits = 0
        candidate_checks = 0

        def visit(node: _IntervalNode | None) -> None:
            nonlocal node_visits, candidate_checks
            if node is None or node.max_end <= start:
                return
            node_visits += 1

            if node.left is not None and node.left.max_end > start:
                visit(node.left)

            candidate_checks += 1
            row = node.record
            if row.start < end and row.end > start:
                matches.append(row.ref)

            # Every record in the right subtree starts at or after this node.
            # Once the current start reaches the query end, none can overlap.
            if row.start < end:
                visit(node.right)

        visit(self._root)
        result = tuple(sorted(matches))
        return result, OverlapQueryReceipt(
            start=start,
            end=end,
            match_count=len(result),
            node_visits=node_visits,
            candidate_checks=candidate_checks,
        )

    def overlapping(self, start: int, end: int) -> tuple[str, ...]:
        result, _receipt = self.overlapping_with_receipt(start, end)
        return result


__all__ = ["IntervalRecord", "OverlapQueryReceipt", "TokenIntervalIndex"]
