import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMBINED = ROOT / "scripts/diagnose_sparse_frontier_transition_work.py"
CANDIDATE = ROOT / "scripts/diagnose_sparse_frontier_candidate_work.py"
RETENTION = ROOT / "scripts/diagnose_sparse_frontier_actor_retention_work.py"
REWRITE = ROOT / "scripts/diagnose_sparse_frontier_rewrite_work.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_diagnostic_scripts_are_python_syntax_valid() -> None:
    for path in (COMBINED, CANDIDATE, RETENTION, REWRITE):
        ast.parse(_source(path), filename=str(path))


def test_combined_receipt_requires_candidate_retention_and_rewrite_measurements() -> (
    None
):
    source = _source(COMBINED)

    assert "candidate_work_receipt" in source
    assert "actor_retention_work_receipt" in source
    assert "rewrite_work_receipt" in source
    assert '"object_candidate_conjunctive_exposure"' in source
    assert '"actor_retention_conjunctive_exposure"' in source
    assert '"bounded_top_k_ranking"' in source
    assert '"incremental_candidate_and_resolution_lifecycle"' in source
    assert '"beta_write_rows_per_semantic_delta"' in source
    assert '"requires_sql_change_this_round": False' in source


def test_candidate_probe_measures_complete_exposure_ranking_and_rewrite_funnel() -> (
    None
):
    source = _source(CANDIDATE)

    for token in (
        "required_key_rows",
        "profile_key_rows",
        "unary_key_match_rows",
        "partial_profile_rows",
        "unary_conjunctive_rows",
        "direct_static_conjunctive_rows",
        "direct_recency_candidate_rows",
        "current_helper_candidate_rows",
        "raw_candidate_rows",
        "deduplicated_rows",
        "ranked_rows",
        "max_candidate_survivors",
        "candidate_rows_rewritten_by_canonical",
        "candidate_semantic_delta_rows",
        "beta_unary_partial_key_rows_per_final_object_candidate",
        "beta_rank_raw_rows_per_survivor",
        "beta_write_candidate_rows_per_semantic_delta",
    ):
        assert token in source

    assert "EXCEPT ALL" in source
    assert "row_number() OVER" in source
    assert "candidate_ordinal < ranked.max_candidates" in source
    assert "demand.lexical_symbol_id = profile.head_symbol_id" in source
    assert "demand.lexical_symbol_id = profile.predicate_symbol_id" in source


def test_candidate_probe_surfaces_selectivity_wildcards_and_plan_spill() -> None:
    source = _source(CANDIDATE)

    assert "candidate_mask_histogram" in source
    assert "required_key_count_histogram" in source
    assert "recency_histogram" in source
    assert "max_candidates_histogram" in source
    assert "broadest_profile_postings" in source
    assert "broadest_demand_postings" in source
    assert "wildcard_rows" in source
    assert '"ANALYZE, BUFFERS, WAL, FORMAT JSON"' in source
    assert "temp_read_blocks" in source
    assert "temp_written_blocks" in source
    assert "shared_hit_blocks" in source


def test_actor_retention_probe_preserves_three_axis_semantics_and_measures_fanout() -> (
    None
):
    source = _source(RETENTION)

    assert "2^3 = 8 masks" in source
    assert "profile.factor_type_symbol_id" in source
    assert "profile.object_kind_symbol_id" in source
    assert "profile.role_symbol_id" in source
    assert "lexical" in source.lower()
    assert "_UNARY_MATCH" in source
    assert "_PARTIAL_PROFILE" in source
    assert "_COMPOSITE_MATCH" in source
    assert "indexed_numeric_pnf_demanded_actor_profiles" in source
    assert "helper_composite_cardinality_parity" in source
    assert "beta_unary_rows_per_retained_profile" in source
    assert "wildcard_rows" in source


def test_rewrite_probe_measures_no_change_update_and_resolution_amplification() -> None:
    source = _source(REWRITE)

    assert "candidate_count_update_rows" in source
    assert "candidate_count_semantic_delta_rows" in source
    assert "unique_resolution_update_rows" in source
    assert "unique_resolution_semantic_delta_rows" in source
    assert "canonical_delete_insert_rows" in source
    assert "resolution_semantic_delta_rows" in source
    assert "EXCEPT ALL" in source
    assert "beta_rewrite_rows_per_semantic_delta" in source
    assert "created_at is excluded" in source


def test_diagnostics_are_read_only_and_do_not_install_an_optimization() -> None:
    candidate = _source(CANDIDATE).upper()
    retention = _source(RETENTION).upper()
    rewrite = _source(REWRITE).upper()

    for source in (candidate, retention, rewrite):
        assert "SET TRANSACTION READ ONLY" in source
        assert "CREATE OR REPLACE FUNCTION" not in source
        assert "CREATE INDEX" not in source
        assert "ALTER TABLE" not in source
        assert "DELETE FROM EXECUTION." not in source
        assert "UPDATE EXECUTION." not in source
        assert "INSERT INTO EXECUTION." not in source
