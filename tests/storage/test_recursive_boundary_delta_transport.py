from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark_recursive_boundary_delta_transport.py"
MIGRATION_073 = ROOT / "database" / "postgres_migrations" / "073_parent_delta_projection.sql"
MIGRATION_075 = ROOT / "database" / "postgres_migrations" / "075_complete_parent_delta_boundary.sql"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_b2_reads_only_boundary_and_structural_topology() -> None:
    source = _source().casefold()
    for required in (
        "semantic_pnf_region",
        "semantic_pnf_interface",
        "semantic_pnf_interface_export",
        "semantic_pnf_interface_lookup",
        "semantic_pnf_parent_delta_projection",
        "semantic_pnf_parent_delta_lookup_projection",
    ):
        assert required in source
    for forbidden in (
        "semantic_parser_token",
        "semantic_pnf_object as",
        "semantic_pnf_factor as",
        "semantic_pnf_hyperedge",
        "semantic_pnf_demand as",
        "semantic_pnf_actor_profile",
    ):
        assert forbidden not in source


def test_b2_checks_exact_transport_and_fusion_homomorphism() -> None:
    source = _source()
    assert "direct_exports - projected_exports" in source
    assert "projected_exports - direct_exports" in source
    assert "direct_lookups - projected_lookups" in source
    assert "projected_lookups - direct_lookups" in source
    assert "_fuse_export_rows" in source
    assert "_fused_export_view" in source
    assert "_fuse_lookup_rows" in source
    assert "_fused_lookup_view" in source
    assert '"fusion_naturality_equal": parity_equal' in source


def test_b2_work_receipt_forbids_interior_rescan_and_per_hop_global_lookup() -> None:
    source = _source()
    assert '"source_interior_rescan_count": 0' in source
    assert '"global_lookup_per_hop_count": 0' in source
    assert '"hierarchy_hop_count": child_interface_hops' in source
    assert '"transported_delta_count"' in source
    assert '"fusion_input_count"' in source


def test_transport_trigger_sources_do_not_reopen_interiors_or_global_lookup() -> None:
    export_source = MIGRATION_073.read_text(encoding="utf-8").casefold()
    lookup_source = MIGRATION_075.read_text(encoding="utf-8").casefold()
    for required in (
        "transport_numeric_pnf_export_delta_insert",
        "transport_numeric_pnf_export_delta_update",
        "transport_numeric_pnf_export_delta_delete",
        "for each statement",
    ):
        assert required in export_source
    for required in (
        "transport_numeric_pnf_lookup_delta_insert",
        "transport_numeric_pnf_lookup_delta_update",
        "transport_numeric_pnf_lookup_delta_delete",
        "for each statement",
    ):
        assert required in lookup_source

    export_transport = export_source[
        export_source.index(
            "create or replace function execution.transport_numeric_pnf_export_delta_insert"
        ) : export_source.index(
            "create or replace function execution.seed_numeric_pnf_parent_delta_projection"
        )
    ]
    lookup_transport = lookup_source[
        lookup_source.index(
            "create or replace function execution.transport_numeric_pnf_lookup_delta_insert"
        ) : lookup_source.index(
            "-- extend fixture/bootstrap to the complete export and lookup boundary"
        )
    ]
    for normal_transport in (export_transport, lookup_transport):
        for forbidden in (
            "semantic_parser_token",
            "semantic_pnf_object as",
            "semantic_pnf_factor as",
            "semantic_pnf_hyperedge",
            "semantic_pnf_global_lookup",
            "semantic_pnf_visible_lookup",
        ):
            assert forbidden not in normal_transport


def test_b2_preserves_root_only_lookup_authority() -> None:
    source = _source()
    assert "semantic_pnf_global_lookup" in source
    assert "semantic_pnf_visible_lookup" in source
    assert "region_kind <> %s" in source
    assert '"root_only_global_lookup"' in source
    assert '"root_only_visible_lookup"' in source


def test_b2_is_read_only_and_creates_no_second_authority() -> None:
    source = _source().casefold()
    assert "set transaction read only" in source
    assert "insert into execution." not in source
    assert "update execution." not in source
    assert "delete from execution." not in source
    assert '"independent_semantic_authority_created": false' in source
