from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION_030 = (
    ROOT / "database" / "postgres_migrations" / "030_durable_work_item_resume.sql"
)
MIGRATION_032 = (
    ROOT / "database" / "postgres_migrations" / "032_typed_semantic_execution.sql"
)
MIGRATION_033 = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "033_remove_execution_json_defaults.sql"
)
MIGRATION_036 = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "036_harden_execution_blob_rejection.sql"
)


def test_durable_work_tables_are_declared() -> None:
    sql = MIGRATION_030.read_text(encoding="utf-8")
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


def test_typed_execution_relations_are_declared() -> None:
    sql = MIGRATION_032.read_text(encoding="utf-8")
    expected = (
        "semantic_job_input_ref",
        "semantic_job_coverage_requirement",
        "semantic_job_assumption",
        "semantic_streaming_operator_job_input",
        "semantic_streaming_operator_token",
        "semantic_typed_value_root",
        "semantic_typed_value_node",
        "semantic_solver_receipt",
        "semantic_solver_receipt_ref",
        "semantic_factor_proposal",
        "semantic_factor_proposal_ref",
        "semantic_factor_proposal_role",
        "semantic_solver_receipt_proposal",
        "semantic_stage_manifest_child",
    )
    for table in expected:
        assert "execution." + table in sql


def test_typed_outbox_triggers_have_no_blob_builders() -> None:
    sql = MIGRATION_032.read_text(encoding="utf-8").casefold()
    assert "semantic.delta.admitted.v2" in sql
    assert "semantic.work-item.completed.v2" in sql
    assert "semantic.publication.committed.v2" in sql
    assert "jsonb_build_object" not in sql
    assert "::jsonb" not in sql


def test_execution_blob_columns_are_rejected_for_new_writes() -> None:
    sql = MIGRATION_036.read_text(encoding="utf-8")
    for table, column in (
        ("semantic_closure_job", "input_manifest"),
        ("semantic_immutable_delta", "payload"),
        ("semantic_round_manifest", "manifest"),
        ("semantic_finalization_cursor", "manifest"),
        ("semantic_publication", "manifest"),
        ("semantic_execution_receipt", "payload"),
        ("semantic_work_item", "input_manifest"),
        ("semantic_work_receipt", "payload"),
        ("semantic_stage_cursor", "cursor_manifest"),
        ("semantic_stage_manifest", "child_work_refs"),
        ("semantic_outbox", "payload"),
    ):
        assert f"ON execution.{table}" in sql
        assert f"NEW.{column} IS NOT NULL" in sql
    assert "reject_execution_blob_write" in sql
    assert "NEW.input_manifest" not in sql.split(
        "CREATE FUNCTION execution.reject_execution_blob_write()", 1
    )[1].split("$$;", 1)[0]


def test_default_removal_migration_does_not_install_polymorphic_triggers() -> None:
    sql = MIGRATION_033.read_text(encoding="utf-8")
    assert "CREATE TRIGGER" not in sql
    assert "CREATE OR REPLACE FUNCTION" not in sql
    assert "NEW.input_manifest" not in sql
    assert "migration 036" in sql


def test_legacy_empty_blob_defaults_are_removed() -> None:
    sql = MIGRATION_033.read_text(encoding="utf-8")
    assert "semantic_run" in sql and "lifecycle_history DROP DEFAULT" in sql
    assert "semantic_kernel_registration" in sql
    assert "metadata DROP DEFAULT" in sql
    assert "semantic_lifecycle_event" in sql
    assert "detail DROP DEFAULT" in sql
    assert "semantic_worker_receipt" in sql
    assert "payload DROP DEFAULT" in sql
