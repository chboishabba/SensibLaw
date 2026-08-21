from __future__ import annotations

import json

import pytest

from src.policy.live_region_close_explain import (
    _ExplainCapture,
    _RegionCloseExplainCursor,
    _global_close_ordinal,
    _is_region_close_update,
    _parse_ordinals,
)


_CLOSE_SQL = """
UPDATE execution.semantic_pnf_region
   SET closure_state = %s,
       graph_revision = %s,
       closed_at = CURRENT_TIMESTAMP
 WHERE region_id = %s
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
                        "Triggers": [{"Trigger Name": "close"}],
                        "Plan": {"Shared Hit Blocks": 3, "WAL Records": 4},
                    }
                ],
            )
        return self

    def fetchone(self):
        row = self._next_row
        self._next_row = None
        return row


def _capture() -> _ExplainCapture:
    return _ExplainCapture(
        ordinal=100,
        work_id=11,
        region_id=22,
        graph_revision=8,
        preclose={"region_id": 22},
        triggers=[],
    )


def test_parse_ordinals_is_positive_unique_and_sorted() -> None:
    assert _parse_ordinals("12600, 100,6355") == (100, 6355, 12600)


def test_region_close_match_is_specific_to_canonical_close_shape() -> None:
    assert _is_region_close_update(_CLOSE_SQL) is True
    assert (
        _is_region_close_update(
            "UPDATE execution.semantic_pnf_region SET closure_state = %s WHERE region_id = %s"
        )
        is False
    )


def test_selected_close_executes_explain_analyze_instead_of_duplicate_update() -> None:
    base = _FakeCursor()
    capture = _capture()
    cursor = _RegionCloseExplainCursor(base, capture)

    returned = cursor.execute(_CLOSE_SQL, (2, 8, 22))

    assert returned is cursor
    assert len(base.executed) == 1
    assert base.executed[0][0].startswith(
        "EXPLAIN (ANALYZE, BUFFERS, WAL, VERBOSE, SETTINGS, FORMAT JSON) UPDATE"
    )
    assert capture.raw_plan is not None


def test_non_close_sql_passes_through_unchanged() -> None:
    base = _FakeCursor()
    cursor = _RegionCloseExplainCursor(base, _capture())

    cursor.execute("SELECT 1", None)

    assert base.executed == [("SELECT 1", None)]


def test_global_ordinal_survives_a_new_process_counter(tmp_path) -> None:
    state = tmp_path / "ordinal-state.json"
    ordinals = (512, 1024, 2048)

    assert _global_close_ordinal(state_path=state, ordinals=ordinals) == 1
    assert _global_close_ordinal(state_path=state, ordinals=ordinals) == 2
    assert json.loads(state.read_text()) == {
        "configured_ordinals": [512, 1024, 2048],
        "contract_ref": "sensiblaw.live-region-close-explain-ordinal-state.v0_1",
        "last_reserved_ordinal": 2,
    }


def test_global_ordinal_refuses_state_from_another_diagnostic(tmp_path) -> None:
    state = tmp_path / "ordinal-state.json"
    _global_close_ordinal(state_path=state, ordinals=(512,))

    with pytest.raises(RuntimeError, match="belongs to another diagnostic"):
        _global_close_ordinal(state_path=state, ordinals=(1024,))
