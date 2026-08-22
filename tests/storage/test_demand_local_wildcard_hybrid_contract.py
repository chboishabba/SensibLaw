from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/diagnose_sparse_frontier_demand_local_hybrid.py"
).read_text()


def test_probe_is_read_only_and_temp_only() -> None:
    assert '"semantic_mutation_performed": False' in SCRIPT
    assert '"temp_state_only": True' in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_temporal_restriction_precedes_object_position_quotient() -> None:
    assert '"temporal_operator_order": "restrict_demand_then_quotient_object_position"' in SCRIPT
    assert "lead(grouped.last_end_char)" in SCRIPT
    assert "d.demand_position < s.next_end_char" in SCRIPT
    assert "s.last_end_char <= d.demand_position" in SCRIPT


def test_exact_legacy_demand_position_rule_is_used() -> None:
    assert "COALESCE(demand.source_start_char, source_region.end_char)" in SCRIPT
    assert "JOIN execution.semantic_pnf_region AS source_region" in SCRIPT
    assert '"demand_position_rule": "coalesce_source_start_char_source_region_end_char"' in SCRIPT


def test_equal_position_representatives_remain_score_intervals() -> None:
    assert "GROUP BY profile.object_id, profile.last_end_char" in SCRIPT
    assert "AS score_min" in SCRIPT
    assert "AS score_max" in SCRIPT
    assert "representative_rows" in SCRIPT
    assert "carrier_row_conservation" in SCRIPT


def test_kth_boundary_uses_only_active_demand_local_segments() -> None:
    assert "AS cutoff_end" in SCRIPT
    assert "OFFSET (d.max_candidates - 1)" in SCRIPT
    assert "OFFSET d.max_candidates" in SCRIPT
    assert "has_overflow" in SCRIPT
    assert "s.next_end_char IS NULL" in SCRIPT


def test_must_may_certificate_is_computed_only_at_cutoff_fibre() -> None:
    assert "cutoff_candidate AS MATERIALIZED" in SCRIPT
    assert "certain_outrankers" in SCRIPT
    assert "possible_outrankers" in SCRIPT
    assert "x.score_min > c.score_max" in SCRIPT
    assert "x.score_max > c.score_min" in SCRIPT
    assert "may_in AND NOT must_in" in SCRIPT


def test_certified_path_uses_an_attained_witness_not_score_authority() -> None:
    assert "ORDER BY s.last_end_char DESC, s.score_min DESC, s.object_id" in SCRIPT
    assert '"bounded_witness_score": "score_min_attained_but_not_semantic_authority"' in SCRIPT
    assert '"consumer_authority": "membership_count_unique_target_outcome_membership_provenance"' in SCRIPT


def test_cartesian_legacy_oracle_is_no_longer_required() -> None:
    assert '"legacy_cartesian_oracle_required": False' in SCRIPT
    assert "raw_candidate AS MATERIALIZED" not in SCRIPT
    assert "wildcard_legacy_membership" not in SCRIPT


def test_persisted_candidates_are_only_a_non_authoritative_crosscheck() -> None:
    assert "execution.semantic_pnf_demand_candidate" in SCRIPT
    assert '"persisted_crosscheck_authority": "non_authoritative_anomaly_signal_only"' in SCRIPT
    assert "persisted_crosscheck_membership_mismatches" in SCRIPT


def test_probe_fails_closed_on_carrier_or_partition_defect() -> None:
    assert "valid = carrier_row_conservation and partition_exact" in SCRIPT
    assert "return 0 if valid else 2" in SCRIPT
    assert "hybrid_partition_exact" in SCRIPT
