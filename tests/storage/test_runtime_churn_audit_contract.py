from pathlib import Path

from src.storage.postgres.runtime_churn_audit import (
    TableChurnReceipt,
    _query_templates,
    build_runtime_churn_delta,
)


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


def test_runtime_churn_delta_requires_same_statistics_identity() -> None:
    before = {
        "database": "strict",
        "postmaster_started_at": "2026-08-20T00:00:00+00:00",
        "stats_reset_at": None,
        "schemas": ["execution", "resolution"],
        "tables": [],
    }
    after = {**before, "database": "different"}

    assert build_runtime_churn_delta(before, after)["state"] == "unknown"


def test_runtime_churn_delta_reports_only_new_counter_work() -> None:
    common = {
        "database": "strict",
        "postmaster_started_at": "2026-08-20T00:00:00+00:00",
        "stats_reset_at": None,
        "schemas": ["execution", "resolution"],
    }
    before = {
        **common,
        "tables": [
            {
                "schema_name": "execution",
                "table_name": "projection",
                "inserts": 10,
                "updates": 5,
                "deletes": 1,
                "sequential_scans": 2,
                "index_scans": 3,
                "live_rows": 9,
                "dead_rows": 1,
            }
        ],
    }
    after = {
        **common,
        "tables": [
            {
                **before["tables"][0],
                "inserts": 17,
                "updates": 9,
                "deletes": 2,
                "sequential_scans": 4,
                "index_scans": 8,
                "live_rows": 15,
                "dead_rows": 2,
            }
        ],
    }

    delta = build_runtime_churn_delta(before, after)

    assert delta["state"] == "measured"
    assert delta["totals"] == {
        "inserts": 7,
        "updates": 4,
        "deletes": 1,
        "sequential_scans": 2,
        "index_scans": 5,
        "total_mutations": 12,
    }
    assert delta["tables"][0]["live_rows_before"] == 9
    assert delta["tables"][0]["live_rows_after"] == 15


def test_query_template_sql_escapes_literal_percent_for_psycopg() -> None:
    required_columns = (
        "query",
        "calls",
        "rows",
        "total_exec_time",
        "mean_exec_time",
        "shared_blks_hit",
        "shared_blks_read",
        "shared_blks_dirtied",
        "shared_blks_written",
        "temp_blks_read",
        "temp_blks_written",
        "queryid",
        "wal_records",
        "wal_bytes",
    )

    class Cursor:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []
            self._fetchall = iter(
                (
                    [(column,) for column in required_columns],
                    [
                        (
                            1,
                            "UPDATE execution.semantic_pnf_region SET closure_state = $1",
                            2,
                            2,
                            4.0,
                            2.0,
                            1,
                            0,
                            0,
                            0,
                            0,
                            0,
                            1,
                            2,
                        )
                    ],
                )
            )

        def execute(self, statement: str, params: object = None) -> None:
            self.calls.append((statement, params))

        def fetchone(self) -> tuple[bool, str]:
            return True, "pg_stat_statements"

        def fetchall(self) -> list[tuple[object, ...]]:
            return next(self._fetchall)

    cursor = Cursor()
    templates = _query_templates(cursor, limit=7)

    assert templates[0].query_id == 1
    statement, params = cursor.calls[-1]
    assert "ILIKE '%%execution.%%'" in statement
    assert params == (7,)
