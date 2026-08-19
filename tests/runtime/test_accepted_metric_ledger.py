from src.runtime.accepted_metric_ledger import (
    MetricGate,
    build_accepted_metric_ledger,
)
from src.runtime.performance_constitution import assess_replay_run


def _timed_run(*, parser_ns: int = 1000, post_ns: int = 100) -> dict:
    return {
        "completed": True,
        "parity": {"semantic_parity": True},
        "numeric_work_timing": {
            "spacy_parser_wall_occupancy_ns": parser_ns,
            "post_parser_wall_occupancy_ns": post_ns,
            "parser_post_overlap_ns": 25,
            "spacy_parser_only_wall_ns": parser_ns - 25,
            "post_parser_only_wall_ns": max(0, post_ns - 25),
            "hierarchy_work_ns": 30,
            "lookup_publication_ns": 10,
            "timing_basis": "process-active-work+monotonic-wall-occupancy:v3",
        },
    }


def test_accepted_metric_passes_only_from_explicit_occupancy() -> None:
    ledger = build_accepted_metric_ledger(_timed_run())
    assert ledger.gate is MetricGate.PASS
    assert ledger.parser_relative_ratio == 0.1
    assert ledger.phases.hierarchy_work_ns == 30


def test_missing_parser_relative_measurement_is_unknown_not_pass() -> None:
    run = {
        "completed": True,
        "parity": {"semantic_parity": True},
        "outer_phase_seconds": {"LOCAL_PNF_COMPILATION": 6358.0},
    }
    ledger = build_accepted_metric_ledger(run)
    assessment = assess_replay_run(run)
    assert ledger.gate is MetricGate.UNKNOWN
    assert assessment["semantic_gate"] == "pass"
    assert assessment["performance_gate"] == "unknown"
    assert assessment["accepted_performance"] is False


def test_completed_semantic_run_can_fail_performance_gate() -> None:
    assessment = assess_replay_run(_timed_run(post_ns=101))
    assert assessment["semantic_gate"] == "pass"
    assert assessment["performance_gate"] == "fail"
    assert assessment["accepted_performance"] is False


def test_nested_compilation_parser_receipt_is_accepted() -> None:
    run = {
        "compilation": {
            "artifacts": {
                "parser_receipt": _timed_run()["numeric_work_timing"]
            }
        }
    }
    assert build_accepted_metric_ledger(run).gate is MetricGate.PASS
