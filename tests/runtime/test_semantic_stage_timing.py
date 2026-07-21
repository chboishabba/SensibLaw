from __future__ import annotations

from src.runtime.stage_timing import StageTimingLedger


def test_stage_timing_reports_throughput_and_reduction_efficiency() -> None:
    ledger = StageTimingLedger(document_ref="document:timing")
    with ledger.stage("base_proposal_reduction", backend_ref="python") as stage:
        stage.record(
            input_edges=100,
            output_edges=25,
            input_nodes=80,
            output_nodes=20,
            tokens_processed=500,
            proposals_generated=80,
            duplicates_collapsed=10,
            residuals_emitted=3,
        )

    row = ledger.to_dict()["timings"][0]
    assert row["stage"] == "base_proposal_reduction"
    assert row["reduction_ratio"] == 0.75
    assert row["tokens_processed"] == 500
    assert row["reduction_efficiency_edges_per_second"] is not None or row["elapsed_ms"] == 0
    assert ledger.to_dict()["stage_totals_ms"]["base_proposal_reduction"] >= 0
