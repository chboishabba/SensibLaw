from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M092 = ROOT / "database/postgres_migrations/092_consumer_sufficient_context_and_tape.sql"
M093 = ROOT / "database/postgres_migrations/093_controlled_learning_and_tape_wiring.sql"


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_hot_projection_verifier_is_symmetric_for_all_three_projections() -> None:
    sql = _sql(M092)
    # Each current table must appear in both directions of EXCEPT equality.
    assert sql.count("semantic_pnf_candidate_current_execution") >= 2
    assert sql.count("semantic_pnf_candidate_current_admissibility") >= 2
    assert sql.count("semantic_pnf_candidate_current_preference") >= 2
    assert "FROM execution.semantic_pnf_candidate_current_admissibility\n     EXCEPT" in sql
    assert "FROM execution.semantic_pnf_candidate_current_preference\n     EXCEPT" in sql


def test_context_attachment_requires_positive_typed_fit_and_never_admits_identity() -> None:
    sql = _sql(M092)
    assert "semantic_pnf_world_candidate_requirement" in sql
    assert "semantic_pnf_world_context_axis_symbol" in sql
    assert "requirements_satisfied" in sql
    assert "candidate context requirements are not positively witnessed" in sql
    attachment_body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.attach_numeric_pnf_world_candidate", 1
    )[1].split("$$;", 1)[0]
    assert "admit_numeric_pnf_external_identity_alignment" not in attachment_body


def test_consumer_sufficiency_stops_execution_without_mutating_demand_state() -> None:
    sql = _sql(M092)
    body = sql.split(
        "CREATE OR REPLACE FUNCTION execution.advance_numeric_pnf_horizon_work_for_consumer", 1
    )[1].split("$$;", 1)[0]
    assert "numeric_pnf_consumer_stop_at_horizon" in body
    assert "INSERT INTO execution.semantic_pnf_horizon_work_queue" in body
    assert "UPDATE execution.semantic_pnf_demand" not in body
    assert "resolved_target_id" not in body


def test_controlled_learning_requires_workload_consumer_and_config_identity() -> None:
    sql = _sql(M092) + _sql(M093)
    assert "workload_digest" in sql
    assert "consumer_ref" in sql
    assert "compiler_config_digest" in sql
    assert "controlled workload token carrier changed" in sql
    assert "identical controlled workload, consumer, and compiler configuration" in sql


def test_tape_registration_cannot_self_certify_exactness() -> None:
    sql = _sql(M093)
    registration = sql.split(
        "CREATE OR REPLACE FUNCTION execution.register_numeric_parser_tape", 1
    )[1].split("$$;", 1)[0]
    assert "exact_roundtrip_verified" in registration
    assert "FALSE" in registration
    assert "verify_registered_numeric_parser_tape" in sql
