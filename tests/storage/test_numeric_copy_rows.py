from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from src.storage.postgres.numeric_copy_rows import _sql_identifier, copy_numeric_rows


ROOT = Path(__file__).resolve().parents[2]
COPY_ROWS = ROOT / "src/storage/postgres/numeric_copy_rows.py"
PROJECTION = ROOT / "src/storage/postgres/spacy_numeric_projection.py"


class _Copy:
    def __init__(self) -> None:
        self.rows: list[tuple[object, ...]] = []

    def write_row(self, row) -> None:
        self.rows.append(tuple(row))


class _Cursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, object | None]] = []
        self.copy_sql: list[str] = []
        self.copy_rows: list[tuple[object, ...]] = []

    def execute(self, sql: str, params=None) -> None:
        self.statements.append((sql, params))

    @contextmanager
    def copy(self, sql: str):
        self.copy_sql.append(sql)
        copy = _Copy()
        yield copy
        self.copy_rows.extend(copy.rows)


def test_numeric_copy_uses_zero_row_typed_ctas_without_catalog_introspection() -> None:
    cursor = _Cursor()
    copy_numeric_rows(
        cursor,
        table="semantic_parser_token",
        columns=("token_ref", "token_id"),
        rows=(("t1", 1), ("t2", 2)),
    )

    executed = "\n".join(sql for sql, _ in cursor.statements)
    assert (
        "CREATE TEMP TABLE tmp_parser_token ON COMMIT DROP AS "
        "SELECT token_ref, token_id FROM execution.semantic_parser_token WITH NO DATA"
        in executed
    )
    assert "information_schema" not in executed
    assert "ALTER TABLE" not in executed
    assert cursor.copy_sql == [
        "COPY tmp_parser_token (token_ref, token_id) FROM STDIN"
    ]
    assert cursor.copy_rows == [("t1", 1), ("t2", 2)]
    assert (
        "INSERT INTO execution.semantic_parser_token (token_ref, token_id) "
        "SELECT token_ref, token_id FROM tmp_parser_token ON CONFLICT DO NOTHING"
        in executed
    )


def test_numeric_copy_empty_batch_performs_zero_database_work() -> None:
    cursor = _Cursor()
    copy_numeric_rows(
        cursor,
        table="semantic_parser_token",
        columns=("token_ref",),
        rows=(),
    )
    assert cursor.statements == []
    assert cursor.copy_sql == []


@pytest.mark.parametrize(
    "value",
    ("", "1table", "table-name", "table;drop", "table name", 'table"name'),
)
def test_internal_sql_identifier_fails_closed_without_regex(value: str) -> None:
    with pytest.raises(ValueError, match="invalid internal SQL identifier"):
        _sql_identifier(value)


def test_strict_numeric_projection_uses_numeric_copy_helper_not_legacy_helper() -> None:
    source = PROJECTION.read_text(encoding="utf-8")
    assert (
        "from src.storage.postgres.numeric_copy_rows import copy_numeric_rows as _copy_rows"
        in source
    )
    assert "from src.storage.postgres.spacy_parser_store import (\n    _copy_rows," not in source


def test_numeric_copy_helper_contains_no_catalog_or_regex_path() -> None:
    source = COPY_ROWS.read_text(encoding="utf-8")
    assert "information_schema" not in source
    assert "ALTER TABLE" not in source
    assert "import re" not in source
    assert "re." not in source
