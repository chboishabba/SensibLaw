from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/084_limit_composition_pairs_before_ranking.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_pair_limit_is_nested_inside_ranking_layer() -> None:
    source = _source()
    assert "numeric_pnf_bounded_local_composition_pairs" in source
    assert "numeric_pnf_bounded_entity_composition_pairs" in source
    assert source.count("AS limited") >= 2
    assert source.count("LIMIT max_per_bridge") >= 2
    assert "row_number() OVER" in source


def test_final_refresh_uses_bounded_pair_helpers() -> None:
    source = _source()
    refresh = source.split(
        "CREATE OR REPLACE FUNCTION execution.refresh_numeric_pnf_factor_composition_candidates",
        1,
    )[1]
    assert "numeric_pnf_bounded_local_composition_pairs" in refresh
    assert "numeric_pnf_bounded_entity_composition_pairs" in refresh
    assert "semantic_pnf_factor_composition_overflow" in refresh


def test_bounded_helpers_remain_document_scoped() -> None:
    source = _source()
    assert "region.run_id = selected_run_id" in source
    assert "region.document_id = selected_document_id" in source
    assert "semantic_pnf_global_lookup" not in source
