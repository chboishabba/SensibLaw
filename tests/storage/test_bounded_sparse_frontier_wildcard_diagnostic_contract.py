from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "diagnose_sparse_frontier_bounded_wildcard.py"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_bounded_wildcard_probe_is_pre_promotion_and_temp_only() -> None:
    source = _source()
    assert "sensiblaw.sparse-frontier-bounded-wildcard-diagnostic.v0_1" in source
    assert '"semantic_mutation_performed": False' in source
    assert '"temp_state_only": True' in source
    assert "CREATE TEMP TABLE wildcard_profile_ordered" in source
    assert "INSERT INTO execution." not in source
    assert "UPDATE execution." not in source
    assert "DELETE FROM execution." not in source


def test_bounded_wildcard_uses_exact_legacy_survivor_order() -> None:
    source = _source()
    assert "PARTITION BY candidate.demand_id" in source
    assert "candidate.structural_distance" in source
    assert "candidate.candidate_score DESC" in source
    assert "candidate.index_rank" in source
    assert "candidate.target_id" in source
    assert "candidate_ordinal < ranked.max_candidates" in source


def test_bounded_wildcard_prefix_is_k_times_measured_multiplicity() -> None:
    source = _source()
    assert "SELECT COALESCE(max(row_count), 0)::BIGINT" in source
    assert "GROUP BY object_id" in source
    assert "LIMIT demand.max_candidates * {multiplicity_bound}" in source
    assert "last_end_char DESC" in source
    assert "candidate_score DESC" in source


def test_bounded_wildcard_fails_closed_on_legacy_representative_ambiguity() -> None:
    source = _source()
    assert "ambiguous_nearest_object_representatives" in source
    assert "HAVING min(profile.candidate_score)" in source
    assert "IS DISTINCT FROM max(profile.candidate_score)" in source
    assert '"status": "fail_closed"' in source


def test_bounded_wildcard_is_currently_scoped_to_recency_class_three() -> None:
    source = _source()
    assert "count(*) FILTER (WHERE recency_class <> 3)" in source
    assert "non_recency_class_3_demands" in source
    assert "profile.last_end_char <= demand.demand_position" in source


def test_bounded_wildcard_parity_is_resumable_and_exact() -> None:
    source = _source()
    assert "EXCEPT ALL" in source
    assert "legacy_minus_bounded" in source
    assert "bounded_minus_legacy" in source
    assert "exact_survivor_parity" in source
    assert "global_exact_survivor_parity" in source
    assert "--batch-size" in source
    assert "connection.autocommit = True" in source
