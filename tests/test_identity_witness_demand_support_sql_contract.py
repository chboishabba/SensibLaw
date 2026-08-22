from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M111 = (
    ROOT
    / "database/postgres_migrations/111_identity_witness_demand_support_projection.sql"
)


def test_identity_witnesses_are_not_backfilled_into_demand_ownership() -> None:
    sql = M111.read_text(encoding="utf-8")
    assert "UPDATE execution.semantic_pnf_identity_witness" not in sql
    assert "semantic_pnf_identity_witness_demand_support_v1" in sql


def test_demand_attribution_uses_only_explicit_object_or_exact_token_support() -> None:
    sql = M111.read_text(encoding="utf-8")
    assert "witness.demand_id IS NOT NULL" in sql
    assert "demand.source_object_id=witness.source_object_id" in sql
    assert "demand_support.token_id=witness_support.token_id" in sql
    assert "semantic_pnf_object_token_support" in sql
    assert "symbol_text" not in sql
    assert "semantic_symbol" not in sql
    assert (
        "paragraph"
        not in sql.lower().split(
            "create or replace view execution.semantic_pnf_identity_witness_demand_support_v1",
            1,
        )[1]
    )
    assert "LIKE" not in sql
    assert "regexp" not in sql.lower()


def test_accepted_projection_requires_explicit_admission() -> None:
    sql = M111.read_text(encoding="utf-8")
    accepted = sql.split(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_accepted_identity_witness_demand_support_v1",
        1,
    )[1].split(";", 1)[0]
    assert "admission_state=2" in accepted
