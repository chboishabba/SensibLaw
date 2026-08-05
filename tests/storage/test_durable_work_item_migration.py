from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "030_durable_work_item_resume.sql"
)
OUTBOX = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "027_semantic_execution_outbox_triggers.sql"
)


def test_durable_work_tables_are_declared() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    expected = (
        "semantic_stage_instance",
        "semantic_work_item",
        "semantic_work_dependency",
        "semantic_work_attempt_v2",
        "semantic_artifact_segment",
        "semantic_stage_cursor",
        "semantic_stage_manifest",
        "semantic_work_receipt",
        "semantic_coordinator_lease",
    )
    for table in expected:
        assert "execution." + table in sql


def test_work_completion_has_outbox_trigger() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "semantic.work-item.completed.v1" in sql
    assert "AFTER UPDATE OF state ON execution.semantic_work_item" in sql


def test_strict_delta_admission_has_matching_outbox_trigger() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "execution.semantic_strict_delta_admission" in sql
    assert "semantic.delta.admitted.v1" in sql
    assert "NEW.prior_revision" in sql
    assert "NEW.resulting_revision" in sql
    assert "NEW.lease_epoch" in sql


def test_publication_trigger_uses_live_state_column() -> None:
    sql = OUTBOX.read_text(encoding="utf-8")
    assert "NEW.state <> 'committed'" in sql
    assert "OLD.state = 'committed'" in sql
    assert "NEW.state_ref" not in sql
    assert "semantic_delta_admission_outbox" in sql
    assert "DROP FUNCTION IF EXISTS execution.emit_semantic_delta_admitted" in sql
