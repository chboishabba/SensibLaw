from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/diagnose_sparse_frontier_hybrid_consumer_parity_cost.py"
).read_text()


def test_contract_is_read_only_and_temp_only() -> None:
    assert '"semantic_mutation_performed": False' in SCRIPT
    assert '"temp_state_only": True' in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_only_certified_demands_enter_bounded_and_legacy_comparison() -> None:
    assert "WHERE d.certified" in SCRIPT
    assert '"legacy_residual_fallback_demands"' in SCRIPT
    assert '"fallback_partition_untouched"' in SCRIPT


def test_membership_and_source_provenance_are_compared_two_way() -> None:
    assert "wildcard_bounded_membership" in SCRIPT
    assert "wildcard_legacy_membership" in SCRIPT
    assert "EXCEPT ALL" in SCRIPT
    assert '"bounded_minus_legacy_memberships"' in SCRIPT
    assert '"legacy_minus_bounded_memberships"' in SCRIPT
    assert "source_interface_id" in SCRIPT


def test_consumer_tuple_derives_count_unique_target_and_outcome() -> None:
    assert "candidate_count" in SCRIPT
    assert "unique_target_id" in SCRIPT
    assert "outcome_state" in SCRIPT
    assert '"derived_consumer_tuple_parity"' in SCRIPT
    assert '"full_consumer_tuple_parity"' in SCRIPT


def test_candidate_score_is_not_promoted_to_semantic_authority() -> None:
    assert (
        '"candidate_score_authority": "execution_metadata_not_semantic_evidence"'
        in SCRIPT
    )
    assert "candidate_score" not in SCRIPT.split("wildcard_bounded_membership", 1)[1].split(
        "wildcard_legacy_membership", 1
    )[0]


def test_legacy_recomputation_preserves_historical_dedup_and_rank_order() -> None:
    assert "ORDER BY candidate.structural_distance" in SCRIPT
    assert "candidate.index_rank" in SCRIPT
    assert "candidate.source_interface_id" in SCRIPT
    assert "candidate.candidate_score DESC" in SCRIPT
    assert "candidate.target_id" in SCRIPT


def test_temporal_shadow_hazard_is_audited() -> None:
    assert "shadowed_certified_demands" in SCRIPT
    assert "g.last_end_char > d.demand_position" in SCRIPT
    assert "p.last_end_char <= d.demand_position" in SCRIPT
    assert (
        '"temporal_eligibility_rule": '
        '"representative_must_be_selected_after_demand_position_filter"'
        in SCRIPT
    )


def test_cost_receipt_separates_bounded_and_legacy_work() -> None:
    assert '"decision_certificate_ms"' in SCRIPT
    assert '"bounded_membership_ms"' in SCRIPT
    assert '"legacy_membership_recompute_ms"' in SCRIPT
    assert '"bounded_path_observed_ms"' in SCRIPT
    assert '"legacy_comparison_observed_ms"' in SCRIPT


def test_probe_fails_closed_on_consumer_tuple_mismatch() -> None:
    assert "return 0 if full_consumer_tuple_parity and fallback_untouched else 2" in SCRIPT
    assert "mismatch_samples" in SCRIPT
    assert (
        '"authoritative_claim": (\n                    '
        '"promotion_blocked_until_full_consumer_tuple_parity_and_cost_win"'
        in SCRIPT
    )
