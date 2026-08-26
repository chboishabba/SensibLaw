from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_region_close_publication.py"


def test_region_close_diagnostic_is_explicitly_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "sensiblaw.region-close-publication-diagnostic.v0_1" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert '"analyze_executed": False' in source
    assert "UPDATE execution.semantic_pnf_region" in source
    assert "EXPLAIN (VERBOSE, COSTS, FORMAT JSON)" in source
    assert "EXPLAIN ANALYZE" not in source


def test_region_close_diagnostic_reports_trigger_work_families() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "interface_aggregation",
        "child_interface_scanning",
        "demand_reconciliation",
        "hierarchy_propagation",
        "recurrence_mention_derivation",
        "parent_closure",
        "global_lookup",
        "revision_publication",
    ):
        assert marker in source


def test_region_close_diagnostic_does_not_delete_or_mutate_rows() -> None:
    source = SCRIPT.read_text(encoding="utf-8").lower()
    assert "delete from" not in source
    assert "insert into" not in source
    assert "alter table" not in source
