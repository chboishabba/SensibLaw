from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "181_canonical_candidate_witness_reduction.sql"
)


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_candidate_witness_reduction_prefers_highest_score_after_distance() -> None:
    source = _source()
    expected = """ORDER BY candidate.structural_distance,
                            candidate.candidate_score DESC,
                            candidate.index_rank,
                            candidate.source_interface_id"""
    assert expected in source


def test_candidate_witness_patch_is_fail_closed() -> None:
    source = _source()
    assert "cannot find execution.rebuild_numeric_pnf_parent_frontier_canonical" in source
    assert "refuses to patch an unrecognised candidate witness ordering" in source
    assert "replacement made no change" in source
    assert "more than one unresolved legacy witness ordering" in source


def test_candidate_witness_patch_does_not_redefine_candidate_membership() -> None:
    source = _source()
    assert "candidate membership" in source
    assert "typed constraints" in source
    assert "recency" in source
    assert "under-specified representative choice" in source
    assert "DELETE FROM execution.semantic_pnf_demand_candidate" not in source
    assert "INSERT INTO execution.semantic_pnf_demand_candidate" not in source


def test_candidate_score_is_documented_as_execution_not_semantic_evidence() -> None:
    source = _source()
    assert "Migration 086 already classifies candidate_score as planner/execution state" in source
    assert "not semantic signed evidence" in source
