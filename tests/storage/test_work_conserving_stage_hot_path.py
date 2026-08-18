from __future__ import annotations

from types import SimpleNamespace

from src.storage.postgres.work_conserving_stage_hot_path import (
    summarize_document_persistence,
)


def test_summary_keeps_execution_only_stage_phase_timings() -> None:
    runtime = SimpleNamespace(
        stage_refs=[],
        dsn=None,
        staged_row_count=0,
        row_expansion_ns=0,
        stage_preparation_ns_by_family={"pnf_graph_superbatch": 23},
        stage_admission_ns_by_family={"pnf_graph_superbatch": 11},
    )

    summary = summarize_document_persistence(runtime)

    assert summary["stage_preparation_ns_by_family"] == {"pnf_graph_superbatch": 23}
    assert summary["stage_admission_ns_by_family"] == {"pnf_graph_superbatch": 11}
