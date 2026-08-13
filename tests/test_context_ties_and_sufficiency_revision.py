from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M095 = ROOT / "database/postgres_migrations/095_context_ties_and_sufficiency_revision.sql"
STORE = ROOT / "src/storage/postgres/consumer_sufficient_runtime_store.py"


def _sql() -> str:
    return M095.read_text(encoding="utf-8")


def test_context_choice_requires_unique_top_satisfied_candidate() -> None:
    sql = _sql()
    assert "semantic_pnf_world_context_choice_v1" in sql
    assert "top_satisfied_count=1" in sql
    assert "unique_preference" in sql
    attachment = sql.split(
        "CREATE OR REPLACE FUNCTION execution.attach_numeric_pnf_world_candidate", 1
    )[1].split("$$;", 1)[0]
    assert "choice.unique_preference" in attachment
    assert "admit_numeric_pnf_external_identity_alignment" not in attachment


def test_sufficiency_uses_latest_active_revision_and_policy_safe_kind() -> None:
    sql = _sql()
    assert "semantic_pnf_consumer_sufficiency_current_v1" in sql
    assert "certificate.revision DESC" in sql
    stop = sql.split(
        "CREATE OR REPLACE FUNCTION execution.numeric_pnf_consumer_stop_at_horizon", 1
    )[1].split("$$;", 1)[0]
    assert "certificate.certificate_state=1" in stop
    assert "selected_policy_ref='' AND certificate.certificate_kind IN (1,3)" in stop
    assert "selected_policy_ref<>'' AND certificate.certificate_kind IN (2,3)" in stop


def test_sufficiency_recorder_is_append_only() -> None:
    sql = _sql()
    recorder = sql.split(
        "CREATE OR REPLACE FUNCTION execution.record_numeric_pnf_consumer_sufficiency", 1
    )[1].split("$$;", 1)[0]
    assert "INSERT INTO execution.semantic_pnf_consumer_sufficiency_certificate" in recorder
    assert "ON CONFLICT" not in recorder
    assert "UPDATE execution.semantic_pnf_consumer_sufficiency_certificate" not in recorder


def test_python_gateway_uses_append_only_sql_recorder() -> None:
    source = STORE.read_text(encoding="utf-8")
    method = source.split("def record_consumer_sufficiency", 1)[1].split(
        "def withdraw_consumer_sufficiency", 1
    )[0]
    assert "record_numeric_pnf_consumer_sufficiency" in method
    assert "INSERT INTO" not in method
