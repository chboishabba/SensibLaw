from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/diagnose_sparse_frontier_wildcard_interval_abstention.py"
).read_text()


def test_contract_is_read_only_and_temp_only() -> None:
    assert "semantic_mutation_performed\": False" in SCRIPT
    assert "temp_state_only\": True" in SCRIPT
    assert "CREATE TEMP TABLE wildcard_interval_profile" in SCRIPT
    assert "CREATE TEMP TABLE wildcard_object_nearest_interval" in SCRIPT
    lowered = SCRIPT.lower()
    assert "insert into execution." not in lowered
    assert "update execution." not in lowered
    assert "delete from execution." not in lowered


def test_nearest_ties_are_carried_as_score_intervals() -> None:
    assert "min(profile.candidate_score) AS score_min" in SCRIPT
    assert "max(profile.candidate_score) AS score_max" in SCRIPT
    assert "representative_rows" in SCRIPT
    assert "score_interval_objects" in SCRIPT


def test_no_score_preferred_representative_is_selected() -> None:
    nearest_section = SCRIPT.split("wildcard_object_nearest_interval", 1)[1]
    assert "DISTINCT ON" not in nearest_section
    assert "score_min" in nearest_section
    assert "score_max" in nearest_section


def test_exact_envelope_is_computed_at_the_kth_distance_fibre() -> None:
    assert "AS cutoff_end" in SCRIPT
    assert "remaining_slots" in SCRIPT
    assert "cutoff_candidates" in SCRIPT
    assert "p.last_end_char > b.cutoff_end" in SCRIPT
    assert "b.eligible_count > b.max_candidates" in SCRIPT


def test_must_membership_uses_all_possible_outrankers() -> None:
    assert "possible_outrankers < remaining_slots AS must_in" in SCRIPT
    assert "x.score_max > c.score_min" in SCRIPT
    assert "x.score_max = c.score_min" in SCRIPT
    assert "x.object_id < c.object_id" in SCRIPT


def test_may_membership_uses_only_certain_outrankers() -> None:
    assert "certain_outrankers < remaining_slots AS may_in" in SCRIPT
    assert "x.score_min > c.score_max" in SCRIPT
    assert "x.score_min = c.score_max" in SCRIPT
    assert "x.object_id < c.object_id" in SCRIPT


def test_ambiguity_causes_abstention_not_semantic_choice() -> None:
    assert "abstaining_demands" in SCRIPT
    assert "c.may_in AND NOT c.must_in" in SCRIPT
    assert '"membership_envelope": "must_subset_realized_subset_may"' in SCRIPT
    assert (
        '"authoritative_claim": "all_realizations_only_when_must_equals_may"'
        in SCRIPT
    )


def test_endpoint_only_observer_is_not_used_as_authority() -> None:
    assert "optimistic AS" not in SCRIPT
    assert "pessimistic AS" not in SCRIPT
    assert "all-minimum and all-maximum endpoint rankings" in SCRIPT


def test_probe_is_scoped_to_observed_wildcard_recency_class() -> None:
    assert "expected_target_kind = 1" in SCRIPT
    assert "expected_factor_type_symbol_id IS NULL" in SCRIPT
    assert "expected_object_kind_symbol_id IS NULL" in SCRIPT
    assert "role_symbol_id IS NULL" in SCRIPT
    assert "lexical_symbol_id IS NULL" in SCRIPT
    assert "recency_class = 3" in SCRIPT
