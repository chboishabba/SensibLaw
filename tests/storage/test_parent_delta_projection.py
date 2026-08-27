from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database/postgres_migrations/073_parent_delta_projection.sql"
BENCHMARK = ROOT / "scripts/benchmark_parent_delta_projection.py"


def _migration() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_parent_delta_projection_is_shadow_not_canonical_authority() -> None:
    source = _migration()
    assert "semantic_pnf_parent_delta_projection" in source
    assert "semantic_pnf_parent_delta_fused_export" in source
    assert "rebuild_numeric_pnf_parent_frontier" not in source
    assert "semantic_pnf_frontier_resolution" not in source
    assert "semantic_pnf_actor_profile" not in source


def test_export_changes_transport_setwise_without_child_interior_rescan() -> None:
    source = _migration()
    for required in (
        "REFERENCING NEW TABLE AS inserted_export",
        "REFERENCING OLD TABLE AS deleted_export",
        "REFERENCING OLD TABLE AS old_export NEW TABLE AS new_export",
        "FOR EACH STATEMENT",
        "semantic_pnf_interface_export",
        "child.parent_region_id",
    ):
        assert required in source
    for forbidden in (
        "semantic_parser_token",
        "semantic_pnf_object AS",
        "semantic_pnf_factor AS",
        "semantic_pnf_hyperedge",
    ):
        assert forbidden not in source


def test_fusion_is_parent_local_associative_projection() -> None:
    source = _migration()
    view_start = source.index(
        "CREATE OR REPLACE VIEW execution.semantic_pnf_parent_delta_fused_export"
    )
    view_end = source.index(
        "CREATE OR REPLACE FUNCTION execution.transport_numeric_pnf_export_delta_insert",
        view_start,
    )
    view = source[view_start:view_end]
    assert "GROUP BY parent_region_id, export_kind, target_kind, target_id" in view
    assert "min(rank)" in view
    assert "max(promotion_score)" in view
    assert "count(*) AS contributing_child_count" in view


def test_reparenting_moves_delta_atoms_without_reopening_child() -> None:
    source = _migration()
    assert "rehome_numeric_pnf_parent_delta_projection" in source
    assert "AFTER UPDATE OF parent_region_id" in source
    assert "SET parent_region_id = NEW.parent_region_id" in source
    assert "WHERE child_region_id = NEW.region_id" in source


def test_seed_is_explicit_boundary_only_bootstrap() -> None:
    source = _migration()
    start = source.index("seed_numeric_pnf_parent_delta_projection")
    seed = source[start:]
    assert "semantic_pnf_interface_export AS export" in seed
    assert "semantic_parser_token" not in seed
    assert "semantic_pnf_object" not in seed
    assert "semantic_pnf_factor" not in seed


def test_benchmark_is_read_only_and_limits_claim_scope() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in source
    assert '"database_mutations_performed": False' in source
    assert '"canonical_parent_frontier_mutated": False' in source
    assert '"whole_parent_frontier_equality_claimed": False' in source
    assert '"source_token_rescan_count": 0' in source
    assert '"source_object_rescan_count": 0' in source
    assert '"source_factor_rescan_count": 0' in source
