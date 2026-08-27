from __future__ import annotations

from dataclasses import replace

import pytest

from src.pnf.numeric_hyperfabric import WorkOperation
from src.storage.postgres.numeric_adjacent_reconciliation import (
    execute_adjacent_lease,
    execute_adjacent_lease_tranche,
)
from src.storage.postgres.numeric_hyperfabric_store import WorkLease


class _Cursor:
    def __init__(
        self,
        row: tuple[int] | None = (701,),
        rows: tuple[tuple[int, int], ...] = ((1, 701),),
    ) -> None:
        self.row = row
        self.rows = rows
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, statement: str, parameters: tuple[object, ...]) -> None:
        self.statements.append((statement, parameters))

    def fetchone(self) -> tuple[int] | None:
        return self.row

    def fetchall(self) -> tuple[tuple[int, int], ...]:
        return self.rows


def _lease(
    *,
    work_id: int = 101,
    region_id: int = 202,
    lease_token: str = "lease-token",
    lease_epoch: int = 3,
) -> WorkLease:
    return WorkLease(
        work_id=work_id,
        region_id=region_id,
        operation=WorkOperation.ADJACENT_RECONCILE,
        lease_token=lease_token,
        lease_epoch=lease_epoch,
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


def test_adjacent_tranche_is_one_recursive_ordered_server_fold() -> None:
    leases = (
        _lease(),
        _lease(
            work_id=102,
            region_id=203,
            lease_token="lease-token-2",
            lease_epoch=7,
        ),
    )
    cursor = _Cursor(rows=((1, 701), (2, 702)))

    assert execute_adjacent_lease_tranche(cursor, leases) == (701, 702)
    assert len(cursor.statements) == 1
    statement, parameters = cursor.statements[0]
    lowered = statement.casefold()
    assert "with recursive" in lowered
    assert "input.ordinal = prior.ordinal + 1" in lowered
    assert "execute_numeric_pnf_adjacent_work" in statement
    assert "ORDER BY ordinal" in statement
    assert parameters == (
        [101, 102],
        ["lease-token", "lease-token-2"],
        [3, 7],
    )


def test_adjacent_tranche_rejects_non_adjacent_work() -> None:
    cursor = _Cursor()
    bad = replace(_lease(), operation=WorkOperation.SENTENCE_CLOSE)

    with pytest.raises(ValueError, match="requires adjacent-reconcile leases"):
        execute_adjacent_lease_tranche(cursor, (_lease(), bad))
    assert cursor.statements == []


def test_adjacent_tranche_requires_complete_ordered_results() -> None:
    leases = (
        _lease(),
        _lease(work_id=102, region_id=203, lease_token="b", lease_epoch=4),
    )

    with pytest.raises(RuntimeError, match="incomplete ordered executor result"):
        execute_adjacent_lease_tranche(_Cursor(rows=((1, 701),)), leases)

    with pytest.raises(RuntimeError, match="executor order changed"):
        execute_adjacent_lease_tranche(
            _Cursor(rows=((2, 702), (1, 701))),
            leases,
        )


def test_adjacent_tranche_empty_input_is_noop() -> None:
    cursor = _Cursor()
    assert execute_adjacent_lease_tranche(cursor, ()) == ()
    assert cursor.statements == []
