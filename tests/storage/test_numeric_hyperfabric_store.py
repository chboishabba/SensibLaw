from __future__ import annotations

import pytest

from src.storage.postgres.numeric_hyperfabric_store import _load_sentence_tokens


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def execute(self, _query: str, _parameters: tuple[int, ...]) -> None:
        pass

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


def test_sentence_closure_rejects_missing_persisted_dependency_head() -> None:
    cursor = _Cursor(
        [
            (
                41,
                1,
                2,
                3,
                4,
                5,
                None,
                None,
                0,
                4,
            )
        ]
    )

    with pytest.raises(RuntimeError, match="missing dependency head"):
        _load_sentence_tokens(cursor, region_id=9)
