from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NUMERIC = ROOT / "src/policy/numeric_pnf_compilation.py"


def _source() -> str:
    return NUMERIC.read_text(encoding="utf-8")


def _cached_branch(source: str) -> str:
    return source.split("if cached is not None:", 1)[1].split(
        "store.persist_source_document(", 1
    )[0]


def _fresh_tail(source: str) -> str:
    return source.split("authority = compilation.artifacts", 1)[1]


def test_cached_numeric_build_is_execution_reuse_not_fresh_semantic_measurement() -> None:
    branch = _cached_branch(_source())
    assert 'state="reused_numeric_pnf"' in branch
    assert "_record_controlled_reuse(" not in branch
    assert "return cached" in branch


def test_fresh_numeric_build_records_controlled_semantic_work_measurement() -> None:
    tail = _fresh_tail(_source())
    assert "measurement_id = _record_controlled_reuse(" in tail
    assert 'state="compiled_numeric_pnf"' in tail
    assert '"controlled_reuse_measurement_id": measurement_id' in tail


def test_cached_reuse_comment_separates_replay_cost_from_semantic_work() -> None:
    branch = _cached_branch(_source())
    assert "execution-reuse receipt" in branch
    assert "Replay timing/work is measured" in branch
