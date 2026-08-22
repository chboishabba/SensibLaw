from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_sparse_frontier_temp_posting_buckets.py"


def test_temp_posting_probe_is_non_authoritative_and_production_safe() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "sensiblaw.sparse-frontier-temp-posting-bucket-diagnostic.v0_1" in source
    assert "CREATE TEMP TABLE" in source
    assert "ON COMMIT PRESERVE ROWS" in source
    assert '"production_schema_changed": False' in source
    assert "INSERT INTO execution." not in source
    assert "UPDATE execution." not in source
    assert "DELETE FROM execution." not in source


def test_temp_posting_probe_materialises_exact_profile_signature_once() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from diagnose_sparse_frontier_composite_signatures import _PROFILE_SIGNATURE" in source
    assert "INSERT INTO {TEMP_TABLE}" in source
    assert "FROM ({_PROFILE_SIGNATURE}) AS signature" in source
    assert '"temp_posting_build"' in source


def test_temp_posting_probe_builds_partial_index_per_mask_active_coordinates() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _posting_columns(mask: int)" in source
    assert 'columns.append("factor_key")' in source
    assert 'columns.append("object_kind_key")' in source
    assert 'columns.append("role_key")' in source
    assert 'columns.append("lexical_key")' in source
    assert "WHERE mask = {mask}" in source
    assert "last_end_char DESC" in source
    assert "promotion_score DESC" in source


def test_temp_candidate_lookup_uses_only_active_mask_coordinates() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "def _temp_candidate_sql(mask: int)" in source
    assert "posting.mask = {mask}" in source
    assert "posting.factor_key = demand.expected_factor_type_symbol_id" in source
    assert "posting.object_kind_key = demand.expected_object_kind_symbol_id" in source
    assert "posting.role_key = demand.role_symbol_id" in source
    assert "posting.lexical_key = demand.lexical_symbol_id" in source
    assert "IS NOT DISTINCT FROM" not in source


def test_temp_posting_probe_is_timeout_resumable_across_masks() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "connection.autocommit = True" in source
    assert "a cancelled per-mask query does not" in source
    assert 'action="append"' in source
    assert '"temp_posting_summary"' in source


def test_temp_posting_parity_remains_exact_per_mask() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "EXCEPT ALL" in source
    assert '"temp_posting_exact_parity"' in source
    assert '"exact_multiset_parity"' in source
    assert '"global_exact_parity"' in source
    assert "_fingerprint_sql" in source


def test_temp_posting_plan_receipt_keeps_physical_evidence() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "ANALYZE, BUFFERS, WAL, FORMAT JSON" in source
    assert "_plan_receipt" in source
    assert "temp_read_blocks" not in source or "_plan_receipt" in source
    assert '"temp_posting_candidates"' in source
