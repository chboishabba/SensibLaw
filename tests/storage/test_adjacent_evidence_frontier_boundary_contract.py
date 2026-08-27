from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/199_exclude_adjacent_evidence_from_parent_frontier.sql"
)


def test_close_trigger_excludes_overlapping_evidence_fibres() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    evidence_guard = "IF NEW.region_kind IN (2, 4) THEN"
    defer_guard = "current_setting('sensiblaw.defer_frontier_rebuild', true)"
    reducer_call = "rebuild_numeric_pnf_parent_frontier"

    assert evidence_guard in sql
    assert defer_guard in sql
    assert sql.index(evidence_guard) < sql.index(defer_guard)
    assert sql.index(evidence_guard) < sql.index(reducer_call)


def test_document_frontier_carrier_excludes_pair_regions() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "region.region_kind NOT IN (1, 2, 4, 9)" in sql
    assert "child_region.region_kind NOT IN (2, 4, 9)" in sql
    assert "JOIN eligible AS parent" in sql


def test_adjacent_executor_remains_the_evidence_owner() -> None:
    executor = Path(
        "database/postgres_migrations/056_numeric_pnf_adjacent_executor.sql"
    ).read_text(encoding="utf-8")

    assert "pair_row.region_kind NOT IN (2, 4)" in executor
    assert "semantic_pnf_adjacent_candidate_evidence" in executor
    assert "execute_numeric_pnf_adjacent_work" in executor


def test_migration_does_not_redefine_parent_reducer() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert (
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier"
        not in sql
    )
