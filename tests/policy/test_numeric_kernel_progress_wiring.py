from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NUMERIC = ROOT / "src/policy/numeric_pnf_compilation.py"
BENCHMARK = ROOT / "scripts/benchmark_complete_tranche_phases.py"


def test_strict_numeric_compile_wires_streaming_observer_and_sampler() -> None:
    source = NUMERIC.read_text(encoding="utf-8")

    assert "NumericKernelProgressSampler(" in source
    assert "with numeric_streaming_kernel_progress(observer):" in source
    assert "progress_observer=observer" in source
    for kernel in (
        "numeric_authority_extraction",
        "operational_build_publication",
        "semantic_receipt_publication",
    ):
        assert f'kernel="{kernel}"' in source


def test_numeric_stage_stays_open_through_semantic_receipt_publication() -> None:
    source = NUMERIC.read_text(encoding="utf-8")
    body = source.split("def persist_numeric_pnf_document(", 1)[1].split(
        "def canonical_text_sha256", 1
    )[0]

    stage = body.index('progress.stage(\n            "numeric_pnf_compilation"')
    receipt = body.index("persist_completed_numeric_semantic_receipt(")
    completion = body.index('message="numeric_pnf_completed"')
    assert stage < receipt < completion
    assert "advance_outer=False" in body[stage:receipt]


def test_complete_tranche_benchmark_uses_failure_surviving_progress() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")

    assert "DurablePhaseRecorder" in source
    assert '"local_pnf_compile_progress.json"' in source
    assert "runner.PhaseRecorder = TimedDurablePhaseRecorder" in source
