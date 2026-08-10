from pathlib import Path


MIGRATION = Path(
    "database/postgres_migrations/082_bounded_factor_composition_generation.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_composition_generation_bounds_pair_work_before_retention() -> None:
    source = _source()
    assert "CROSS JOIN LATERAL" in source
    assert "LIMIT max_per_bridge" in source
    assert source.count("LIMIT max_per_bridge") >= 2
    assert "semantic_pnf_hyperedge_object_factor_idx" in source
    assert "semantic_pnf_factor_region_factor_idx" in source


def test_composition_overflow_is_explicit_execution_evidence() -> None:
    source = _source()
    assert "semantic_pnf_factor_composition_overflow" in source
    assert "possible_pair_count" in source
    assert "retained_pair_limit" in source
    assert "participant_count * (participant_count - 1)" in source
    assert "bridge_kind = 1" in source
    assert "bridge_kind = 2" in source


def test_composition_refresh_remains_document_scoped() -> None:
    source = _source()
    assert "region.run_id = selected_run_id" in source
    assert "region.document_id = selected_document_id" in source
    assert "semantic_pnf_global_lookup" not in source
    assert "semantic_pnf_visible_lookup" not in source


def test_overflow_does_not_create_semantic_derivation_authority() -> None:
    source = _source()
    assert "semantic_pnf_factor_derivation_rule" not in source
    assert "derivation_state" not in source
    assert "explicitDomainRule" not in source
