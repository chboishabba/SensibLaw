from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_numeric_demand_insert_produces_occurrence_provenance_directly() -> None:
    sql = (
        ROOT
        / "database/postgres_migrations/135_demand_trigger_target_occurrence.sql"
    ).read_text(encoding="utf-8")
    lowered = sql.casefold()

    assert "create trigger semantic_pnf_demand_occurrence_producer" in lowered
    assert "on execution.semantic_pnf_demand" in lowered
    assert "record_numeric_pnf_demand_occurrence_provenance" in lowered
    assert "occurrence_role=1" in lowered
    assert "occurrence_role=2" in lowered
    assert "occurrence_role=3" in lowered
    assert "semantic_pnf_factor_token_support" in lowered
    assert "semantic_pnf_object_token_support" in lowered
    assert "semantic_pnf_hyperedge" in lowered


def test_numeric_occurrence_producer_fails_closed_instead_of_guessing() -> None:
    sql = (
        ROOT
        / "database/postgres_migrations/135_demand_trigger_target_occurrence.sql"
    ).read_text(encoding="utf-8")

    assert "IF producer_match_count<>1" in sql
    assert "IF target_match_count<>1" in sql
    assert "No target-role rule means" in sql
    assert "Do not manufacture an entity occurrence" in sql


def test_numeric_compiler_does_not_depend_on_operational_occurrence_bridge() -> None:
    source = (ROOT / "src/policy/numeric_pnf_compilation.py").read_text(
        encoding="utf-8"
    )

    assert "project_resolution_demand_occurrence_to_numeric_pnf" not in source
    assert "demand_occurrence_store" not in source
    assert "run_streaming_spacy_execution" in source
    assert "semantic_pnf_demand" in source
