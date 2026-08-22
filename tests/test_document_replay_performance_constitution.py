from __future__ import annotations

import json
from pathlib import Path

from scripts import benchmark_document_replay as benchmark
from src.runtime.performance_constitution import assess_replay_run


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts/benchmark_document_replay.py"


def test_replay_benchmark_embeds_performance_constitution() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert "from src.runtime.performance_constitution import assess_replay_run" in source
    assert 'row["performance_constitution"] = assess_replay_run(row)' in source
    assert '"numeric_work_timing": numeric_work_timing' in source


def test_replay_without_explicit_wall_parser_timing_remains_unknown() -> None:
    assessment = assess_replay_run(
        {
            "completed": True,
            "parity": {"semantic_parity": True},
            "kernel_seconds": {"local_typing": 1.0, "closure": 2.0},
            "numeric_work_timing": {
                "timing_basis": "aggregate-process-active-work:v1",
                "spacy_parser_work_seconds": 10.0,
                "post_parser_work_seconds": 1.0,
                "post_parser_to_spacy_work_ratio": 0.1,
            },
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


def test_numeric_work_timing_extracts_latest_durable_progress_event(tmp_path) -> None:
    path = tmp_path / "local_pnf_compile_progress.json"
    path.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "details": {
                            "spacy_parser_work_ns": 4_000_000_000,
                            "post_parser_worker_work_ns": 500_000_000,
                            "post_parser_coordinator_ns": 250_000_000,
                            "post_parser_work_ns": 750_000_000,
                            "timing_basis": "aggregate-process-active-work:v1",
                        }
                    },
                    {
                        "details": {
                            "spacy_parser_work_ns": 8_000_000_000,
                            "post_parser_worker_work_ns": 400_000_000,
                            "post_parser_coordinator_ns": 200_000_000,
                            "post_parser_work_ns": 600_000_000,
                            "timing_basis": "aggregate-process-active-work:v1",
                        }
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    observed = benchmark._numeric_work_timing(path)
    assert observed["spacy_parser_work_seconds"] == 8.0
    assert observed["post_parser_worker_work_seconds"] == 0.4
    assert observed["post_parser_coordinator_seconds"] == 0.2
    assert observed["post_parser_work_seconds"] == 0.6
    assert observed["post_parser_to_spacy_work_ratio"] == 0.075
    assert observed["timing_basis"] == "aggregate-process-active-work:v1"
    assert observed["evidence_path"] == str(path)


def test_numeric_work_timing_missing_ledger_is_unknown_not_zero(tmp_path) -> None:
    observed = benchmark._numeric_work_timing(tmp_path / "missing.json")
    assert observed["spacy_parser_work_seconds"] is None
    assert observed["post_parser_work_seconds"] is None
    assert observed["post_parser_to_spacy_work_ratio"] is None
