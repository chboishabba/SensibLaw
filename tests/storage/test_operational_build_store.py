from __future__ import annotations

from src.storage.postgres.operational_build_store import (
    load_completed_operational_build,
    operational_build_ref,
    persist_completed_operational_build,
)


class Cursor:
    def __init__(self, *, rows=()):
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self._rows = list(rows)
        self._fetch_index = 0

    def execute(self, sql: str, params=None) -> None:
        self.calls.append(
            (" ".join(sql.split()), tuple(params) if params is not None else None)
        )

    def fetchone(self):
        if self._fetch_index >= len(self._rows):
            return None
        row = self._rows[self._fetch_index]
        self._fetch_index += 1
        return row

    def fetchall(self):
        if self._fetch_index >= len(self._rows):
            return []
        rows = self._rows[self._fetch_index]
        self._fetch_index += 1
        return rows


def test_operational_build_ref_is_exact_keyed() -> None:
    first = operational_build_ref(
        document_ref="document:test",
        compiler_contract_ref="postgres-semantic-compiler:v0_7",
        build_key_sha256="00" * 32,
    )
    second = operational_build_ref(
        document_ref="document:test",
        compiler_contract_ref="postgres-semantic-compiler:v0_7",
        build_key_sha256="11" * 32,
    )
    assert first != second


def test_completed_build_replays_exact_demand_refs() -> None:
    cursor = Cursor(rows=[("build:test",), [("demand:a",), ("demand:b",)]])
    demands = load_completed_operational_build(
        cursor,
        document_ref="document:test",
        compiler_contract_ref="postgres-semantic-compiler:v0_7",
        build_key_sha256="00" * 32,
    )
    assert demands == ("demand:a", "demand:b")
    assert bytes.fromhex("00" * 32) in cursor.calls[0][1]


def test_missing_build_is_not_confused_with_zero_demand_build() -> None:
    missing = Cursor(rows=[])
    assert (
        load_completed_operational_build(
            missing,
            document_ref="document:test",
            compiler_contract_ref="postgres-semantic-compiler:v0_7",
            build_key_sha256="00" * 32,
        )
        is None
    )

    zero_demands = Cursor(rows=[("build:test",), []])
    assert load_completed_operational_build(
        zero_demands,
        document_ref="document:test",
        compiler_contract_ref="postgres-semantic-compiler:v0_7",
        build_key_sha256="00" * 32,
    ) == ()


def test_persisted_build_links_all_demands() -> None:
    cursor = Cursor()
    build_ref = persist_completed_operational_build(
        cursor,
        document_ref="document:test",
        compiler_contract_ref="postgres-semantic-compiler:v0_7",
        build_key_sha256="00" * 32,
        graph_ref="pnf:test",
        demand_refs=["demand:b", "demand:a", "demand:a"],
    )
    sql = "\n".join(statement for statement, _params in cursor.calls)
    assert build_ref.startswith("build:")
    assert "INSERT INTO execution.operation" in sql
    assert "INSERT INTO execution.build" in sql
    assert "INSERT INTO execution.document_compilation_build" in sql
    assert sql.count("INSERT INTO execution.document_compilation_build_demand") == 2
