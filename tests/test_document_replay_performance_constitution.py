from __future__ import annotations

from pathlib import Path

from src.runtime.performance_constitution import assess_replay_run


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts/benchmark_document_replay.py"


def test_replay_benchmark_embeds_performance_constitution() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert "from src.runtime.performance_constitution import assess_replay_run" in source
    assert 'row["performance_constitution"] = assess_replay_run(row)' in source


def test_replay_without_explicit_parser_timing_remains_unknown() -> None:
    assessment = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "kernel_seconds": {"local_typing": 1.0, "closure": 2.0},
        }
    )
    requirements = {
        row["requirement_ref"]: row for row in assessment["requirements"]
    }
    assert requirements["post_parser_to_spacy_ratio"]["state"] == "unknown"
    assert assessment["hard_gate"] == "pass"


def test_replay_assessment_never_uses_wall_subtraction_for_parser_time() -> None:
    assessment = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "wall_seconds": 100.0,
            "kernel_seconds": {"local_typing": 10.0, "closure": 10.0},
        }
    )
    requirement = next(
        row
        for row in assessment["requirements"]
        if row["requirement_ref"] == "post_parser_to_spacy_ratio"
    )
    assert requirement["state"] == "unknown"
    assert "wall subtraction is not accepted" in str(requirement["evidence"])
