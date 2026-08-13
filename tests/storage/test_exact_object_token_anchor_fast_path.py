from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/083_exact_object_token_anchor_fast_path.sql"
)
STORE = Path("src/storage/postgres/numeric_hyperfabric_store.py")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_strict_numeric_closure_persists_exact_object_token_support() -> None:
    source = _text(STORE)
    assert "INSERT INTO execution.semantic_pnf_object_token_support" in source
    assert "object_spec.source_token_id" in source


def test_anchor_prefers_exact_token_support() -> None:
    source = _text(MIGRATION)
    assert "semantic_pnf_object_token_support_token_idx" in source
    assert "exact_support AS MATERIALIZED" in source
    assert "support.token_id = token.token_id" in source
    assert "HAVING count(DISTINCT support.object_id) = 1" in source


def test_span_fallback_only_runs_without_any_exact_support() -> None:
    source = _text(MIGRATION)
    assert "token_with_any_support AS MATERIALIZED" in source
    assert "LEFT JOIN token_with_any_support AS has_support" in source
    assert "has_support.token_id IS NULL" in source
    assert "fallback_candidate" in source


def test_fallback_is_restricted_to_identity_relevant_tokens() -> None:
    source = _text(MIGRATION)
    assert "needed_token AS MATERIALIZED" in source
    assert "pos.symbol_text IN ('PROPN', 'NOUN')" in source
    assert "dep.symbol_text = 'appos'" in source


def test_document_anchor_function_remains_fail_closed() -> None:
    source = _text(MIGRATION)
    assert "numeric_pnf_document_parser_object_anchor" in source
    assert "region.run_id = selected_run_id" in source
    assert "region.document_id = selected_document_id" in source
    assert "semantic_pnf_global_lookup" not in source
    assert "semantic_pnf_visible_lookup" not in source
