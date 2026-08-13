from pathlib import Path

from src.runtime.durable_work_items import _stage_cursor


def test_stage_cursor_contract_is_contiguous_and_typed() -> None:
    source = Path(_stage_cursor.__code__.co_filename).read_text(encoding="utf-8")

    assert "min(ordinal) FILTER (WHERE state <> 'completed') - 1" in source
    assert "count(*) FILTER (WHERE state = 'completed')" in source
    assert "count(*)" in source
    assert "GREATEST(" not in source
    assert "json" not in source.casefold()
