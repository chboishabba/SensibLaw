from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "src" / "policy" / "numeric_parser_projection_hot_path.py"
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "175_producer_complete_numeric_dependency_heads.sql"
)


def test_producer_complete_path_inserts_final_numeric_head_on_first_write() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "numeric_parser_producer_complete_heads_ready" in source
    assert "_allocate_missing_token_ids" in source
    assert '"token_id",\n                    "head_token_id"' in source
    assert (
        "producer-complete numeric token authority failed exact head parity" in source
    )
    assert "_SETWISE_HEADS_READY.set(True)" in source


def test_producer_complete_capability_disables_only_the_redundant_trigger_rewrite() -> (
    None
):
    source = MIGRATION.read_text(encoding="utf-8")

    assert "sensiblaw.producer_complete_numeric_heads" in source
    assert "RETURN NULL" in source
    assert "UPDATE execution.semantic_parser_token AS token" in source
    assert "numeric_parser_producer_complete_heads_ready" in source


def test_generic_and_older_schema_fallbacks_remain_present() -> None:
    policy = POLICY.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    # Migration 150 semantics remain the generic fallback.
    assert "resolve_numeric_parser_dependency_heads" in migration
    assert "count(head.token_id) <> 1" in migration

    # Python still retains the migration-150 and pre-150 paths when migration
    # 175's producer-complete capability is absent.
    assert "if has_setwise_head_projection:" in policy
    assert "updates = original_project_heads(*args, **kwargs)" in policy
    assert "return updates" in policy


def test_direct_path_keeps_canonical_python_dependency_validation() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "updates = original_project_heads(*args, **kwargs)" in source
    assert "producer-complete dependency head is absent from its sentence" in source
    assert "ambiguous sentence-local span" in source
