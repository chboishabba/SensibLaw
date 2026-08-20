from __future__ import annotations

from pathlib import Path

from src.policy.live_token_insert_explain import (
    _TokenInsertCapture,
    _TokenInsertExplainCursor,
    _is_token_insert,
    _parse_ordinals,
)


_TOKEN_INSERT = """
INSERT INTO execution.semantic_parser_token (token_ref, token_id, head_token_id)
SELECT token_ref, token_id, head_token_id
  FROM tmp_parser_token
ON CONFLICT DO NOTHING
""".strip()


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self._next_row = None

    def execute(self, query, params=None, *args, **kwargs):
        self.executed.append((query, params))
        if isinstance(query, str) and query.startswith("EXPLAIN ("):
            self._next_row = (
                [
                    {
                        "Planning Time": 1.0,
                        "Execution Time": 2.0,
                        "Triggers": [
                            {
                                "Trigger Name": "RI_ConstraintTrigger_c",
                                "Time": 0.5,
                                "Calls": 3,
                            }
                        ],
                        "Plan": {"Shared Hit Blocks": 7, "WAL Records": 11},
                    }
                ],
            )
        return self

    def fetchone(self):
        row = self._next_row
        self._next_row = None
        return row


def _capture() -> _TokenInsertCapture:
    return _TokenInsertCapture(
        ordinal=16,
        row_count=3,
        columns=("token_ref", "sentence_id", "token_id", "head_token_id"),
        constraints=[],
        indexes=[],
        triggers=[],
    )


def test_parse_ordinals_positive_unique_sorted() -> None:
    assert _parse_ordinals("32,1,16") == (1, 16, 32)


def test_token_insert_match_is_specific_to_canonical_copy_insert() -> None:
    assert _is_token_insert(_TOKEN_INSERT) is True
    assert (
        _is_token_insert(
            "INSERT INTO execution.semantic_parser_token (token_ref) VALUES (%s)"
        )
        is False
    )


def test_selected_token_insert_executes_once_under_explain() -> None:
    base = _FakeCursor()
    capture = _capture()
    cursor = _TokenInsertExplainCursor(base, capture)

    returned = cursor.execute(_TOKEN_INSERT)

    assert returned is cursor
    assert len(base.executed) == 1
    assert base.executed[0][0].startswith(
        "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) INSERT"
    )
    assert capture.raw_plan is not None


def test_non_token_insert_passes_through() -> None:
    base = _FakeCursor()
    cursor = _TokenInsertExplainCursor(base, _capture())

    cursor.execute("SELECT 1")

    assert base.executed == [("SELECT 1", None)]


def test_hot_path_installs_token_probe_before_parser_projection() -> None:
    source = Path("src/policy/closure_hot_path_execution.py").read_text()
    token_probe = source.index("install_live_token_insert_explain()")
    parser_projection = source.index("install_numeric_parser_projection_hot_path()")
    assert token_probe < parser_projection


def test_inventory_source_includes_internal_fk_triggers() -> None:
    source = Path("src/policy/live_token_insert_explain.py").read_text()
    assert "trigger.tgisinternal" in source
    assert "NOT trigger.tgisinternal" not in source
    assert "pg_get_constraintdef" in source
    assert "pg_get_indexdef" in source
