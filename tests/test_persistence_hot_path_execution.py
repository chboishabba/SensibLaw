from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.storage.postgres.pipelined_document_cursor import PipelinedDocumentCursor
from src.storage.postgres.stage_copy_codec import STAGE_BINARY_TYPES, write_stage_rows


class _Pipeline:
    def __init__(self) -> None:
        self.sync_calls = 0

    def sync(self) -> None:
        self.sync_calls += 1


class _PipelineContext:
    def __init__(self, pipeline: _Pipeline) -> None:
        self.pipeline = pipeline

    def __enter__(self) -> _Pipeline:
        return self.pipeline

    def __exit__(self, *_args: object) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.pipeline_value = _Pipeline()

    def pipeline(self) -> _PipelineContext:
        return _PipelineContext(self.pipeline_value)


class _RawCursor:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.executed: list[tuple[object, object]] = []
        self._rows = [("ok",)]
        self._rowcount = 3
        self.copy_calls: list[str] = []

    def execute(self, query: object, params: object = None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> object:
        return self._rows[0]

    def fetchall(self) -> list[tuple[str]]:
        return list(self._rows)

    @property
    def rowcount(self) -> int:
        return self._rowcount

    @contextmanager
    def copy(self, sql: str):
        self.copy_calls.append(sql)
        yield object()


class _Copy:
    def __init__(self) -> None:
        self.types: tuple[str, ...] | None = None
        self.rows: list[tuple[object, ...]] = []

    def set_types(self, types: tuple[str, ...]) -> None:
        self.types = tuple(types)

    def write_row(self, row: tuple[object, ...]) -> None:
        self.rows.append(row)


class _CopyCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.copy_value = _Copy()

    @contextmanager
    def copy(self, sql: str):
        self.sql = sql
        yield self.copy_value


def test_pipelined_cursor_syncs_only_when_result_is_observed() -> None:
    raw = _RawCursor()
    with PipelinedDocumentCursor(raw) as cursor:
        cursor.execute("UPDATE a")
        cursor.execute("UPDATE b")
        assert raw.connection.pipeline_value.sync_calls == 0
        assert cursor.fetchone() == ("ok",)
        assert raw.connection.pipeline_value.sync_calls == 1
        cursor.execute("UPDATE c")
        assert cursor.rowcount == 3
        assert raw.connection.pipeline_value.sync_calls == 2

    metrics = cursor.publication_metrics
    assert metrics["statement_count"] == 3
    assert metrics["pipeline_sync_count"] == 2
    assert metrics["fetch_count"] == 1
    assert metrics["execute_ns"] >= 0
    assert metrics["pipeline_sync_ns"] >= 0


def test_pipelined_cursor_records_copy_boundary_without_changing_rows() -> None:
    raw = _RawCursor()
    with PipelinedDocumentCursor(raw) as cursor:
        cursor.execute("UPDATE before_copy")
        with cursor.copy("COPY x FROM STDIN"):
            pass
        cursor.execute("UPDATE after_copy")

    metrics = cursor.publication_metrics
    assert raw.copy_calls == ["COPY x FROM STDIN"]
    assert metrics["statement_count"] == 2
    assert metrics["copy_boundary_count"] == 1
    assert metrics["copy_boundary_ns"] >= 0


def test_stage_binary_type_vector_matches_stage_row_width() -> None:
    assert len(STAGE_BINARY_TYPES) == 27
    assert STAGE_BINARY_TYPES[:5] == ("text",) * 5
    assert STAGE_BINARY_TYPES[5:7] == ("int4", "int8")
    assert STAGE_BINARY_TYPES[7:19] == ("text",) * 12
    assert STAGE_BINARY_TYPES[19:25] == ("int8",) * 6
    assert STAGE_BINARY_TYPES[25:] == ("bytea", "bytea")


def test_binary_copy_sets_exact_types_and_rejects_wrong_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSIBLAW_PERSISTENCE_BINARY_COPY", "1")
    cursor = _CopyCursor()
    row = tuple(range(27))
    write_stage_rows(cursor, "COPY stage FROM STDIN", [row])
    assert cursor.sql.endswith("(FORMAT BINARY)")
    assert cursor.copy_value.types == STAGE_BINARY_TYPES
    assert cursor.copy_value.rows == [row]

    with pytest.raises(ValueError, match="row width"):
        write_stage_rows(_CopyCursor(), "COPY stage FROM STDIN", [(1, 2)])


def test_text_copy_fallback_uses_same_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSIBLAW_PERSISTENCE_BINARY_COPY", "0")
    cursor = _CopyCursor()
    row = tuple(range(27))
    write_stage_rows(cursor, "COPY stage FROM STDIN", [row])
    assert cursor.sql == "COPY stage FROM STDIN"
    assert cursor.copy_value.types is None
    assert cursor.copy_value.rows == [row]
