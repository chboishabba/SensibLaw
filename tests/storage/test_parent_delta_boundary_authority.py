from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "postgres_migrations" / "074_parent_delta_boundary_authority.sql"
BENCHMARK = ROOT / "scripts" / "benchmark_parent_delta_boundary_authority.py"


def test_delta_boundary_owner_is_projection_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    owner_start = source.index(
        "CREATE OR REPLACE FUNCTION execution.numeric_pnf_parent_boundary_atoms"
    )
    parity_start = source.index(
        "CREATE OR REPLACE FUNCTION execution.check_numeric_pnf_parent_boundary_parity"
    )
    owner = source[owner_start:parity_start]
    assert "semantic_pnf_parent_delta_projection" in owner
    for forbidden in (
        "semantic_parser_token",
        "semantic_pnf_object AS",
        "semantic_pnf_factor AS",
        "semantic_pnf_hyperedge",
        "semantic_pnf_global_lookup",
        "rebuild_numeric_pnf_parent_frontier",
    ):
        assert forbidden not in owner


def test_delta_boundary_has_transport_and_fusion_surfaces() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    for required in (
        "numeric_pnf_parent_boundary_atoms",
        "numeric_pnf_parent_fused_boundary",
        "measure_numeric_pnf_parent_delta_boundary",
        "semantic_pnf_parent_delta_fused_export",
        "contributing_child_count",
    ):
        assert required in source


def test_historical_reconstruction_is_certification_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    parity_start = source.index(
        "CREATE OR REPLACE FUNCTION execution.check_numeric_pnf_parent_boundary_parity"
    )
    parity = source[parity_start:]
    assert "semantic_pnf_region AS child_region" in parity
    assert "semantic_pnf_interface AS child_interface" in parity
    assert "semantic_pnf_interface_export AS child_export" in parity
    assert "EXCEPT ALL" in parity
    assert "Normal execution must not call this function" in source


def test_boundary_benchmark_is_read_only_and_scoped() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert "sensiblaw.parent-delta-boundary-authority.v0_1" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert '"canonical_frontier_modified": False' in source
    assert '"parent_local_reconciliation_claimed_equal": False' in source
    assert "EXPLAIN (COSTS, FORMAT JSON)" in source
    assert "EXPLAIN ANALYZE" not in source


def test_boundary_benchmark_has_zero_rescan_gates() -> None:
    source = BENCHMARK.read_text(encoding="utf-8")
    assert '"source_token_rescan_count": 0' in source
    assert '"child_graph_rescan_count": 0' in source
    assert 'receipt["parity"]["equal"]' in source
