from pathlib import Path

from src.runtime.durable_work_item_hardening import _stage_cursor


def test_stage_cursor_contract_is_contiguous() -> None:
    source = Path(_stage_cursor.__code__.co_filename).read_text(encoding="utf-8")

    assert "min(ordinal) FILTER (WHERE state <> 'completed') - 1" in source
    assert "count(*) FILTER (WHERE state = 'completed')" in source
    assert "GREATEST(" not in source
