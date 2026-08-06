from __future__ import annotations

from dataclasses import replace

import pytest

from src.pnf.numeric_hyperfabric import WorkOperation
from src.storage.postgres.numeric_adjacent_reconciliation import (
    execute_adjacent_lease,
)
from src.storage.postgres.numeric_hyperfabric_store import WorkLease


class _Cursor:
    def __init__(self, row: tuple[int] | None = (701,)) -> None:
        self.row = row
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, statement: str, parameters: tuple[object, ...]) -> None:
        self.statements.append((statement, parameters))

    def fetchone(self) -> tuple[int] | None:
        return self.row


def _lease() -> WorkLease:
    return WorkLease(
        work_id=101,
        region_id=202,
        operation=WorkOperation.ADJACENT_RECONCILE,
        lease_token="lease-token",
        lease_epoch=3,
    )


def test_execute_adjacent_lease_uses_the_database_fence() -> None:
    cursor = _Cursor()

    assert execute_adjacent_lease(cursor, _lease()) == 701
    assert len(cursor.statements) == 1
    statement, parameters = cursor.statements[0]
    assert "execute_numeric_pnf_adjacent_work" in statement
    assert parameters == (101, "lease-token", 3)


def test_execute_adjacent_lease_rejects_other_work_kinds() -> None:
    cursor = _Cursor()
    lease = replace(_lease(), operation=WorkOperation.SENTENCE_CLOSE)

    with pytest.raises(
        ValueError,
        match="requires an adjacent-reconcile lease",
    ):
        execute_adjacent_lease(cursor, lease)
    assert cursor.statements == []


def test_execute_adjacent_lease_requires_a_pair_interface_result() -> None:
    cursor = _Cursor(None)

    with pytest.raises(
        RuntimeError,
        match="returned no pair interface",
    ):
        execute_adjacent_lease(cursor, _lease())
