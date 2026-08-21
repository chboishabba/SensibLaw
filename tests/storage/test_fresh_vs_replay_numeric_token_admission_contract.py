from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "src" / "policy" / "numeric_parser_projection_hot_path.py"
COPY = ROOT / "src" / "storage" / "postgres" / "numeric_copy_rows.py"
PROBE = ROOT / "src" / "policy" / "live_token_insert_explain.py"


def test_numeric_copy_returning_is_exact_fresh_admission_surface() -> None:
    source = COPY.read_text(encoding="utf-8")

    assert "returning: Sequence[str] | None = None" in source
    assert 'query += " RETURNING "' in source
    assert "tuple(tuple(row) for row in cursor.fetchall())" in source
    assert "ON CONFLICT DO NOTHING" in source


def test_fresh_path_allocates_without_persistent_token_id_readback() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "_allocate_provisional_token_ids" in source
    assert "FROM generate_series(1, %s)" in source
    assert "SELECT token_ref, token_id\n          FROM execution.semantic_parser_token" not in source
    assert "returning=_RETURNING_COLUMNS" in source


def test_only_conflict_fibre_is_reread_for_exact_replay_parity() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "replay_refs = tuple(" in source
    assert "WHERE token_ref = ANY(%s) AND representation_version = 2" in source
    assert "ORDER BY token_ref FOR KEY SHARE" in source
    assert "persisted != expected" in source
    assert "numeric token replay conflicts with producer-complete authority" in source


def test_mixed_fresh_replay_repairs_only_cross_replay_head_edges() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "head_repairs: list[tuple[int, int]]" in source
    assert "fresh is not None and fresh[-1] != final_head_id" in source
    assert "This path is proportional only to fresh->replay dependency edges" in source


def test_capabilities_are_scoped_with_finally_even_when_insert_fails() -> None:
    source = POLICY.read_text(encoding="utf-8")

    assert "try:\n                returned = original_copy_rows(" in source
    assert "finally:" in source
    assert "_set_producer_reference_capability(cursor, False)" in source
    assert "_set_producer_head_capability(cursor, False)" in source


def test_live_explain_preserves_returning_freshness_without_replaying_insert() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert "def _returning_columns" in source
    assert "xmin::text::bigint = txid_current()" in source
    assert "self._pending_returning" in source
    assert "EXPLAIN ANALYZE executes the real INSERT but suppresses its" in source
