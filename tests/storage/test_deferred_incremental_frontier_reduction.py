from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "postgres_migrations"
    / "072_deferred_incremental_frontier_reduction.sql"
)
PLANNER = ROOT / "src" / "storage" / "postgres" / "numeric_hierarchy_planner.py"


def test_c1_defer_flag_never_defers_sentence_closure() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "current_setting('sensiblaw.defer_frontier_rebuild', true)" in source
    assert "IF NEW.region_kind <> 1 AND defer_frontier_rebuild THEN" in source
    assert "rebuild_numeric_pnf_parent_frontier" in source


def test_c1_document_reducer_skips_exact_already_reduced_revision() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "semantic_pnf_frontier_reduction_receipt" in source
    assert "receipt.interface_id = interface.interface_id" in source
    assert "receipt.graph_revision = interface.graph_revision" in source
    assert "region.region_kind <> 1" in source
    assert "region.region_kind <> 9" in source


def test_c1_hierarchy_enables_transaction_local_deferral() -> None:
    source = PLANNER.read_text(encoding="utf-8")
    flag = '("sensiblaw.defer_frontier_rebuild", "on")'
    assert flag in source
    assert "SELECT set_config(%s, %s, true)" in source


def test_c1_reduces_paragraphs_before_planning_and_upper_fibres_before_publish() -> None:
    source = PLANNER.read_text(encoding="utf-8")
    reducer = "SELECT execution.reduce_numeric_pnf_document_frontiers(%s, %s)"
    first_reduce = source.index(reducer)
    sketch_load = source.index("sketches = _load_paragraph_sketches", first_reduce)
    second_reduce = source.index(reducer, first_reduce + 1)
    ancestor_rebuild = source.index(
        "SELECT execution.rebuild_pnf_document_ancestors(%s, %s)", second_reduce
    )
    visible_refresh = source.index(
        "SELECT execution.refresh_pnf_visible_lookup(%s, %s)", ancestor_rebuild
    )

    assert first_reduce < sketch_load < second_reduce
    assert second_reduce < ancestor_rebuild < visible_refresh


def test_c1_uses_existing_canonical_reducer_not_a_second_authority() -> None:
    planner = PLANNER.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "rebuild_numeric_pnf_parent_frontier" not in planner
    assert migration.count("rebuild_numeric_pnf_parent_frontier") >= 2
    assert "CREATE OR REPLACE FUNCTION execution.rebuild_numeric_pnf_parent_frontier" not in (
        migration
    )
