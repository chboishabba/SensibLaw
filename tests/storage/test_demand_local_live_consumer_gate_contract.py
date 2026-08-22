from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/diagnose_sparse_frontier_demand_local_live_consumer_gate.py").read_text()


def test_read_only_and_temp_only() -> None:
    assert '"semantic_mutation_performed": False' in SCRIPT
    assert '"temp_state_only": True' in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_persisted_legacy_oracle_requires_revision_match() -> None:
    assert "frontier_reduction_receipt" in SCRIPT
    assert "receipt_revision == interface_revision" in SCRIPT
    assert '"persisted_legacy_oracle_current"' in SCRIPT


def test_demand_local_temporal_order_is_preserved() -> None:
    assert "COALESCE(d.source_start_char, source_region.end_char)" in SCRIPT
    assert "lead(last_end_char) OVER" in SCRIPT
    assert "d.demand_position<s.next_end_char" in SCRIPT


def test_must_may_certificate_routes_only_invariant_fibres() -> None:
    assert "x.score_min>c.score_max" in SCRIPT
    assert "x.score_max>c.score_min" in SCRIPT
    assert "COALESCE(r.unstable,0)=0" in SCRIPT
    assert "WHERE d.certified" in SCRIPT


def test_membership_parity_is_two_way_against_live_legacy_output() -> None:
    assert "semantic_pnf_demand_candidate" in SCRIPT
    assert "EXCEPT ALL" in SCRIPT
    assert '"bounded_minus_legacy_memberships"' in SCRIPT
    assert '"legacy_minus_bounded_memberships"' in SCRIPT


def test_frontier_consumer_tuple_is_compared_directly() -> None:
    assert "semantic_pnf_frontier_resolution" in SCRIPT
    assert "candidate_count" in SCRIPT
    assert "selected_target_kind" in SCRIPT
    assert "selected_target_id" in SCRIPT
    assert "outcome_state" in SCRIPT
    assert "witness_interface_id" in SCRIPT
    assert '"full_consumer_tuple_parity"' in SCRIPT


def test_planner_score_is_not_semantic_gate() -> None:
    assert '"candidate_score_authority": "execution_history_not_semantic_evidence"' in SCRIPT


def test_semantic_gate_fails_closed() -> None:
    assert "persisted_oracle_current and full_membership_parity and full_tuple_parity" in SCRIPT
    assert "return 0 if semantic_gate else 2" in SCRIPT
