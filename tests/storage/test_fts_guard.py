from __future__ import annotations

import sqlite3

import pytest

from src.storage.fts import TextIndex


class _FailingConnection:
    def __init__(self) -> None:
        self.row_factory = None

    def execute(self, *_args, **_kwargs):
        raise sqlite3.OperationalError("no such module: fts5")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def close(self) -> None:  # pragma: no cover - close is a no-op in this stub
        return None


def test_text_index_raises_clear_message_when_fts_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sqlite3, "connect", lambda _path: _FailingConnection())

    with pytest.raises(RuntimeError, match="FTS5"):
        TextIndex(tmp_path / "fts.db")
