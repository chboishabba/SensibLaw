from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/145_delta_global_lookup_refresh.sql"
POLICY = ROOT / "src/policy/delta_lookup_publication_execution.py"


def test_delta_refresh_is_scoped_to_explicit_changed_interfaces() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "refresh_pnf_global_lookup_interfaces" in sql
    assert "interface.interface_id = ANY(selected_interface_ids)" in sql
    assert "region.run_ref = selected_run_ref" in sql
    assert "region.document_ref = selected_document_ref" in sql
    assert "DELETE FROM execution.semantic_pnf_global_lookup" in sql
    assert "JOIN execution.semantic_pnf_interface_lookup AS lookup" in sql


def test_delta_refresh_returns_net_row_change_for_exact_total_receipt() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "GET DIAGNOSTICS deleted_count = ROW_COUNT" in sql
    assert "GET DIAGNOSTICS inserted_count = ROW_COUNT" in sql
    assert "RETURN inserted_count - deleted_count" in sql


def test_empty_changed_interface_certificate_is_zero_database_publication() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "if not changed:" in source
    zero_branch = source.split("if not changed:", 1)[1].split("connection = connect", 1)[0]
    assert "return base_rows" in zero_branch


def test_changed_interfaces_are_keyed_by_actual_document_carrier() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "SELECT region.document_ref" in source
    assert "_key(database_url, run_ref, document_ref)" in source
    assert "refresh_pnf_global_lookup_interfaces" in source
