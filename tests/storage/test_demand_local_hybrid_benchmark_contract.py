from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/benchmark_sparse_frontier_demand_local_hybrid.py").read_text()


def test_benchmark_is_temp_only_and_non_mutating() -> None:
    assert '"semantic_mutation_performed": False' in SCRIPT
    assert '"temp_state_only": True' in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_workload_identity_is_demand_profile_pair() -> None:
    assert "--demand-interface-id" in SCRIPT
    assert "--profile-interface-id" in SCRIPT
    assert '"workload_identity"' in SCRIPT
    assert "args.demand_interface_id" in SCRIPT
    assert "args.profile_interface_id" in SCRIPT


def test_hybrid_routes_certified_and_residual_separately() -> None:
    assert "WHERE d.certified" in SCRIPT
    assert "WHERE NOT d.certified" in SCRIPT
    assert '"certified_bounded_demands"' in SCRIPT
    assert '"legacy_residual_fallback_demands"' in SCRIPT


def test_fallback_preserves_historical_dedup_and_rank_order() -> None:
    assert "PARTITION BY r.demand_id,r.target_kind,r.target_id" in SCRIPT
    assert "ORDER BY r.structural_distance,r.index_rank,r.source_interface_id" in SCRIPT
    assert "ORDER BY r.structural_distance,r.candidate_score DESC,r.index_rank,r.target_id" in SCRIPT


def test_full_workload_semantic_gate_compares_membership_and_tuple() -> None:
    assert "hybrid_minus_persisted_memberships" in SCRIPT
    assert "persisted_minus_hybrid_memberships" in SCRIPT
    assert "hybrid_minus_persisted_consumer_tuples" in SCRIPT
    assert "persisted_minus_hybrid_consumer_tuples" in SCRIPT
    assert '"semantic_parity"' in SCRIPT


def test_total_hybrid_cost_includes_setup_certificate_and_route() -> None:
    assert "hybrid_total_median = setup_ms + certificate_ms + hybrid_route_median" in SCRIPT
    assert '"hybrid_total_median_ms"' in SCRIPT
    assert '"setup_ms"' in SCRIPT
    assert '"certificate_ms"' in SCRIPT


def test_legacy_timeout_is_unknown_not_speedup() -> None:
    assert 'legacy_status = "timeout_or_error"' in SCRIPT
    assert '"timeout_semantics": "unknown_not_speedup"' in SCRIPT
    assert "legacy_median is not None and hybrid_total_median < legacy_median" in SCRIPT


def test_promotion_requires_semantic_parity_and_measured_cost_win() -> None:
    assert "promotion_ready = semantic_parity and cost_win" in SCRIPT
    assert '"promotion_rule": "semantic_parity_and_same_pair_measured_full_path_cost_win"' in SCRIPT
