from __future__ import annotations

from pathlib import Path

from src.policy import numeric_pnf_compilation as numeric


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


def test_fresh_numeric_measurement_is_explicitly_observability_gated() -> None:
    tail = _fresh_tail(_source())
    assert "if _controlled_reuse_measurement_enabled():" in tail
    assert "measurement_id = _record_controlled_reuse(" in tail
    assert 'state="compiled_numeric_pnf"' in tail
    assert 'details["controlled_reuse_measurement_id"] = measurement_id' in tail


def test_controlled_learning_observability_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SENSIBLAW_RECORD_CONTROLLED_REUSE", raising=False)
    assert not numeric._controlled_reuse_measurement_enabled()


def test_controlled_learning_observability_can_be_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SENSIBLAW_RECORD_CONTROLLED_REUSE", "1")
    assert numeric._controlled_reuse_measurement_enabled()
