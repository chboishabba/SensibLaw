from pathlib import Path


STORE = Path("src/storage/postgres/numeric_symbol_store.py")


def test_symbol_advisory_locks_only_cover_unresolved_keys() -> None:
    source = STORE.read_text(encoding="utf-8")

    lock_start = source.index("SELECT pg_advisory_xact_lock(")
    insert_start = source.index("INSERT INTO execution.semantic_symbol", lock_start)
    lock_query = source[lock_start:insert_start]

    assert "FROM {temporary} AS requested" in lock_query
    assert "WHERE NOT EXISTS" in lock_query
    assert "FROM execution.semantic_symbol AS symbol" in lock_query
    assert "symbol.kind_id = requested.kind_id" in lock_query
    assert "symbol.symbol_text = requested.symbol_text" in lock_query
    assert "ORDER BY requested.kind_id, requested.symbol_text" in lock_query


def test_symbol_uniqueness_remains_final_admission_authority() -> None:
    source = STORE.read_text(encoding="utf-8")

    assert "ON CONFLICT (kind_id, symbol_text) DO NOTHING" in source
    assert "JOIN {temporary} AS requested" in source
    assert 'RuntimeError("numeric symbol interning returned an incomplete mapping")' in source
