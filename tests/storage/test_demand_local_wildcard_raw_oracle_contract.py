from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/diagnose_sparse_frontier_demand_local_raw_oracle.py"
).read_text()


def test_oracle_is_read_only_and_temp_only() -> None:
    assert '"semantic_mutation_performed": False' in SCRIPT
    assert '"temp_state_only": True' in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_segment_path_applies_temporal_restriction_before_quotient() -> None:
    assert "lead(last_end_char)" in SCRIPT
    assert "s.last_end_char <= d.demand_position" in SCRIPT
    assert "d.demand_position < s.next_end_char" in SCRIPT
    assert '"temporal_operator_order": "restrict_demand_then_quotient_object_position"' in SCRIPT


def test_raw_oracle_selects_nearest_eligible_then_minimum_score_witness() -> None:
    assert "SELECT DISTINCT ON (p.object_id)" in SCRIPT
    assert "p.last_end_char <= d.demand_position" in SCRIPT
    assert "p.last_end_char DESC" in SCRIPT
    assert "p.candidate_score ASC" in SCRIPT
    assert '"witness_realization": "minimum_score_at_nearest_eligible_object_position"' in SCRIPT


def test_segment_and_raw_witness_use_same_final_ranking() -> None:
    assert "ORDER BY s.last_end_char DESC, s.score_min DESC, s.object_id" in SCRIPT
    assert "ORDER BY nearest.last_end_char DESC" in SCRIPT
    assert "nearest.candidate_score DESC" in SCRIPT
    assert "nearest.object_id" in SCRIPT


def test_membership_is_compared_two_way() -> None:
    assert "EXCEPT ALL" in SCRIPT
    assert "segment_minus_raw_memberships" in SCRIPT
    assert "raw_minus_segment_memberships" in SCRIPT
    assert "sample_membership_parity" in SCRIPT


def test_probe_is_bounded_and_fail_closed() -> None:
    assert "--sample-limit" in SCRIPT
    assert "LIMIT %s" in SCRIPT
    assert "return 0 if parity else 2" in SCRIPT
    assert '"sampled_independent_validation_of_temporal_segment_transform_only"' in SCRIPT
