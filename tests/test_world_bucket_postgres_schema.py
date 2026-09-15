from pathlib import Path


MIGRATION = Path("database/postgres_migrations/182_world_bucket_append_only_materialisation.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_world_bucket_schema_is_normalized_and_json_free() -> None:
    sql = _sql().lower()
    for table in (
        "sl_world_bucket",
        "sl_world_bucket_node",
        "sl_world_growth_receipt",
        "sl_world_bucket_projection",
        "sl_world_bucket_projection_member",
        "sl_world_materialisation_receipt",
    ):
        assert f"create table if not exists {table}" in sql

    assert "jsonb" not in sql
    assert " json " not in sql
    assert "payload" not in sql


def test_world_bucket_schema_separates_materialisation_from_authority() -> None:
    sql = _sql().lower()
    assert "materialisation_state" in sql
    for state in (
        "skeleton",
        "reference_only",
        "full_local",
        "cold_local",
        "federated_only",
    ):
        assert state in sql
    assert "candidate_only boolean not null check (candidate_only)" in sql
    assert "semantic_promotion boolean not null check (not semantic_promotion)" in sql
    assert "publication_projection_is_browsing_history boolean not null" in sql
    assert "check (not publication_projection_is_browsing_history)" in sql


def test_world_bucket_tables_reject_update_and_delete() -> None:
    sql = _sql().lower()
    assert "create or replace function sl_reject_world_bucket_mutation()" in sql
    for table in (
        "sl_world_bucket",
        "sl_world_bucket_node",
        "sl_world_growth_receipt",
        "sl_world_bucket_projection",
        "sl_world_bucket_projection_member",
        "sl_world_materialisation_receipt",
    ):
        assert f"before update or delete on {table}" in sql


def test_growth_receipts_and_projection_are_explicitly_typed() -> None:
    sql = _sql().lower()
    assert "edge_family text not null" in sql
    assert "relation text not null" in sql
    assert "cycle boolean not null" in sql
    assert "logical_shard_id text not null" in sql
    assert "content_digest bytea not null" in sql
    assert "source_locator text" in sql
