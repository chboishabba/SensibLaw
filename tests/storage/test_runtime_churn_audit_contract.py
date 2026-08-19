from pathlib import Path

from src.storage.postgres.runtime_churn_audit import TableChurnReceipt


def test_table_churn_amplification_counts_all_physical_mutations() -> None:
    receipt = TableChurnReceipt(
        schema_name="execution",
        table_name="projection",
        inserts=100,
        updates=25,
        deletes=75,
        live_rows=50,
        dead_rows=0,
        sequential_scans=1,
        index_scans=10,
    )
    assert receipt.total_mutations == 200
    assert receipt.churn_amplification == 4.0
    assert receipt.delete_to_live_ratio == 1.5


def test_positive_churn_with_zero_live_rows_fails_ratio_closed() -> None:
    receipt = TableChurnReceipt(
        schema_name="execution",
        table_name="transient_projection",
        inserts=10,
        updates=0,
        deletes=10,
        live_rows=0,
        dead_rows=0,
        sequential_scans=0,
        index_scans=0,
    )
    assert receipt.churn_amplification is None


def test_numeric_compiler_forwards_accepted_timing_fields() -> None:
    source = Path("src/policy/numeric_pnf_compilation.py").read_text(encoding="utf-8")
    for field in (
        "spacy_parser_wall_occupancy_ns",
        "post_parser_wall_occupancy_ns",
        "parser_post_overlap_ns",
        "numeric_projection_worker_work_ns",
        "sentence_closure_worker_work_ns",
        "hierarchy_work_ns",
        "lookup_publication_ns",
        "unclassified_orchestration_wall_ns",
    ):
        assert f'"{field}"' in source
    assert '"numeric_work_timing": timing' in source


def test_attribution_runner_is_repo_root_executable() -> None:
    source = Path("scripts/report_numeric_pnf_runtime_attribution.py").read_text(
        encoding="utf-8"
    )
    assert "Path(__file__).resolve().parents[1]" in source
    assert "sys.path.insert(0, str(REPO_ROOT))" in source
