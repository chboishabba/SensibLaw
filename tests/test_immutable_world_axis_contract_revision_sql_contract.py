from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M115 = (
    ROOT
    / "database/postgres_migrations/115_immutable_world_axis_contract_revisions.sql"
)


def test_same_revision_cannot_change_semantic_contract_coordinates() -> None:
    sql = M115.read_text(encoding="utf-8")
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_world_axis_contract",
        1,
    )[1].split("$$;", 1)[0]
    assert (
        "world-axis contract revision is immutable; increment contract_revision" in body
    )
    for field in (
        "need_kind",
        "provider_id",
        "axis_kind",
        "provider_property_numeric_id",
        "need_revision",
        "priority",
        "minimum_source_epoch",
        "expected_target_kind",
        "expected_factor_type_symbol_id",
        "expected_object_kind_symbol_id",
        "lexical_symbol_id",
        "role_symbol_id",
        "residual_type_symbol_id",
    ):
        assert f"existing.{field} IS DISTINCT FROM selected_{field}" in body


def test_same_revision_may_only_toggle_active_state() -> None:
    sql = M115.read_text(encoding="utf-8")
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_world_axis_contract",
        1,
    )[1].split("$$;", 1)[0]
    assert "SET active=selected_active" in body
    assert "RETURN existing.contract_id" in body
