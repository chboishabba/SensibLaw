from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPLETE_BOUNDARY = (
    ROOT / "database" / "postgres_migrations" / "075_complete_parent_delta_boundary.sql"
)
CANONICAL_REDUCER = (
    ROOT / "database" / "postgres_migrations" / "076_delta_fed_canonical_parent_reducer.sql"
)
BENCHMARK = ROOT / "scripts" / "benchmark_delta_fed_canonical_parent_reducer.py"


def test_complete_boundary_transports_reducer_metadata() -> None:
    source = COMPLETE_BOUNDARY.read_text(encoding="utf-8")
    for required in (
        "scope_class",
        "origin_interface_id",
        "outward_required",
        "semantic_pnf_parent_delta_lookup_projection",
        "semantic_pnf_parent_delta_fused_lookup",
    ):
        assert required in source


def test_lookup_boundary_is_statement_level_delta_fed() -> None:
    source = COMPLETE_BOUNDARY.read_text(encoding="utf-8")
    for required in (
        "REFERENCING NEW TABLE AS inserted_lookup",
        "REFERENCING OLD TABLE AS deleted_lookup",
        "REFERENCING OLD TABLE AS old_lookup NEW TABLE AS new_lookup",
        "FOR EACH STATEMENT",
        "transport_numeric_pnf_lookup_delta_insert",
        "transport_numeric_pnf_lookup_delta_delete",
        "transport_numeric_pnf_lookup_delta_update",
    ):
        assert required in source


def test_reparenting_moves_export_and_lookup_boundaries_together() -> None:
    source = COMPLETE_BOUNDARY.read_text(encoding="utf-8")
    start = source.index(
        "CREATE OR REPLACE FUNCTION execution.rehome_numeric_pnf_parent_delta_projection"
    )
    rehome = source[start:]
    assert "UPDATE execution.semantic_pnf_parent_delta_projection" in rehome
    assert "UPDATE execution.semantic_pnf_parent_delta_lookup_projection" in rehome
    assert "DELETE FROM execution.semantic_pnf_parent_delta_projection" in rehome
    assert "DELETE FROM execution.semantic_pnf_parent_delta_lookup_projection" in rehome


def test_canonical_reducer_consumes_transported_export_boundary() -> None:
    source = CANONICAL_REDUCER.read_text(encoding="utf-8")
    reducer_start = source.index(
        "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier"
    )
    local_start = source.index(
        "-- Everything below is deliberately unchanged parent-local reconciliation.",
        reducer_start,
    )
    boundary_phase = source[reducer_start:local_start]
    assert "semantic_pnf_parent_delta_projection" in boundary_phase
    assert "child_export.parent_region_id = selected_region_id" in boundary_phase
    assert "semantic_pnf_parent_delta_lookup_projection" in boundary_phase
    assert "child_lookup.parent_region_id = selected_region_id" in boundary_phase

    # The old repeated child-interface/export reconstruction must not remain in
    # the boundary phase. Structural child-interface membership is allowed for
    # zero-export actor summaries, but child exports come only from projection.
    assert "JOIN execution.semantic_pnf_interface_export AS child_export" not in boundary_phase


def test_parent_local_nonmonotone_semantics_remain_in_canonical_owner() -> None:
    source = CANONICAL_REDUCER.read_text(encoding="utf-8")
    for required in (
        "semantic_pnf_actor_profile",
        "semantic_pnf_demand_candidate",
        "HAVING count(*) = 1",
        "semantic_pnf_frontier_resolution",
        "candidate_count",
        "resolved_target_id",
        "promotion_threshold",
    ):
        assert required in source


def test_canonical_probe_is_rollback_safe_and_checks_all_authority_surfaces() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert "sensiblaw.delta-fed-canonical-parent-reducer.v0_1" in source
    assert "connection.rollback()" in source
    assert '"probe_transaction_rolled_back": True' in source
    for surface in (
        '"exports"',
        '"lookups"',
        '"actors"',
        '"resolutions"',
        '"demands"',
        '"candidates"',
    ):
        assert surface in source


def test_canonical_probe_has_no_promotion_claim_until_parity() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert '"canonical_authority_promotion_claimed": False' in source
    assert 'receipt["authority_parity"]["equal"]' in source
