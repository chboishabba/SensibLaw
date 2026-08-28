from pathlib import Path

from tools.audit_pg_migration_runtime import audit_migrations


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_superseding_trigger_owner_must_drop_previous_owner(tmp_path: Path) -> None:
    first = _write(
        tmp_path / "001.sql",
        """
        CREATE TRIGGER owner
        AFTER INSERT ON execution.semantic_pnf_demand_candidate
        FOR EACH STATEMENT EXECUTE FUNCTION execution.first_owner();
        """,
    )
    second = _write(
        tmp_path / "002.sql",
        """
        CREATE TRIGGER owner
        AFTER INSERT ON execution.semantic_pnf_demand_candidate
        FOR EACH STATEMENT EXECUTE FUNCTION execution.second_owner();
        """,
    )

    report = audit_migrations([first, second])
    assert report["fatal_count"] == 1
    assert report["fatal"][0]["kind"] == "trigger-owner-collision"


def test_drop_then_statement_replacement_is_clean(tmp_path: Path) -> None:
    first = _write(
        tmp_path / "001.sql",
        """
        CREATE TRIGGER owner
        AFTER INSERT ON execution.semantic_pnf_demand_candidate
        FOR EACH ROW EXECUTE FUNCTION execution.old_owner();
        """,
    )
    second = _write(
        tmp_path / "002.sql",
        """
        DROP TRIGGER IF EXISTS owner ON execution.semantic_pnf_demand_candidate;
        CREATE TRIGGER owner
        AFTER INSERT ON execution.semantic_pnf_demand_candidate
        FOR EACH STATEMENT EXECUTE FUNCTION execution.new_owner();
        """,
    )

    report = audit_migrations([first, second])
    assert report["fatal_count"] == 0
    assert report["active_triggers"][0]["level"] == "statement"


def test_final_hot_row_trigger_is_rejected(tmp_path: Path) -> None:
    migration = _write(
        tmp_path / "001.sql",
        """
        CREATE TRIGGER row_owner
        AFTER INSERT ON execution.semantic_pnf_candidate_execution_event
        FOR EACH ROW EXECUTE FUNCTION execution.row_owner();
        """,
    )

    report = audit_migrations([migration])
    assert report["fatal_count"] == 1
    assert report["fatal"][0]["kind"] == "forbidden-final-row-trigger"
