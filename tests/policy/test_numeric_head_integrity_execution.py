from __future__ import annotations

import pytest

from src.policy.numeric_head_integrity_execution import install_numeric_head_integrity_execution
from src.storage.postgres import numeric_hyperfabric_store as store


class _Cursor:
    def __init__(self, rows):
        self.rows = tuple(rows)
        self.sql = ""
        self.parameters = None

    def execute(self, sql, parameters=None):
        self.sql = str(sql)
        self.parameters = parameters

    def fetchall(self):
        return self.rows


def _row(head):
    return (101, 1, 2, 3, 4, 5, head, None, 10, 14)


def test_numeric_sentence_loader_rejects_null_head() -> None:
    # Installation is idempotent across the suite.
    install_numeric_head_integrity_execution()
    cursor = _Cursor((_row(None),))
    with pytest.raises(RuntimeError, match="missing its explicit numeric head"):
        store._load_sentence_tokens(cursor, 77)


def test_numeric_sentence_loader_preserves_explicit_self_root() -> None:
    install_numeric_head_integrity_execution()
    cursor = _Cursor((_row(101),))
    tokens = store._load_sentence_tokens(cursor, 77)
    assert len(tokens) == 1
    assert tokens[0].head_token_id == tokens[0].token_id == 101
    assert "representation_version = 2" in cursor.sql
