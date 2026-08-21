from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_indexed_sparse_frontier_candidate_parity.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_probe_embeds_literal_legacy_object_candidate_semantics() -> None:
    source = _source()

    assert "_LEGACY_OBJECT_CANDIDATE_SQL" in source
    assert "JOIN execution.semantic_pnf_actor_profile AS profile" in source
    assert "demand.expected_object_kind_symbol_id IS NULL" in source
    assert "demand.role_symbol_id IS NULL" in source
    assert "demand.expected_factor_type_symbol_id IS NULL" in source
    assert "demand.lexical_symbol_id = object.head_symbol_id" in source
    assert "demand.lexical_symbol_id = profile.predicate_symbol_id" in source
    assert "CASE demand.recency_class" in source


def test_probe_compares_complete_candidate_multisets_in_both_directions() -> None:
    source = _source()

    assert "EXCEPT ALL" in source
    assert "legacy_only" in source
    assert "indexed_only" in source
    assert "legacy_count == indexed_count" in source
    assert '"exact_candidate_row_parity"' in source
    assert "structural_distance" in source
    assert "candidate_score" in source


def test_probe_surfaces_wildcard_and_profile_population_for_performance_interpretation() -> None:
    source = _source()

    assert "unconstrained_object_demand_count" in source
    assert "actor_profile_count" in source
    assert "object_demand_count" in source
    assert "expected_factor_type_symbol_id IS NULL" in source
    assert "expected_object_kind_symbol_id IS NULL" in source
    assert "lexical_symbol_id IS NULL" in source
    assert "role_symbol_id IS NULL" in source
