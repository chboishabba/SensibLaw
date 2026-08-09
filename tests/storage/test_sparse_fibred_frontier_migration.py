from pathlib import Path


MIGRATION_ROOT = Path("database/postgres_migrations")
SPARSE_FRONTIER = MIGRATION_ROOT / "062_sparse_fibred_pnf_frontiers.sql"
ACTOR_NORMALISATION = (
    MIGRATION_ROOT / "063_sparse_actor_profile_null_normalisation.sql"
)
ANAPHOR_SURFACE = (
    MIGRATION_ROOT / "064_anaphor_surface_lexical_evidence.sql"
)


def _source() -> str:
    return SPARSE_FRONTIER.read_text(encoding="utf-8")


def test_sparse_frontier_migrations_exist_and_remain_numeric() -> None:
    assert SPARSE_FRONTIER.is_file()
    assert ACTOR_NORMALISATION.is_file()
    assert ANAPHOR_SURFACE.is_file()
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SPARSE_FRONTIER,
            ACTOR_NORMALISATION,
            ANAPHOR_SURFACE,
        )
    ).casefold()
    assert " json " not in source
    assert " jsonb" not in source
    assert "::json" not in source
    assert "json_build" not in source


def test_closed_fibres_have_typed_sparse_boundary_objects() -> None:
    source = _source()
    for required in (
        "semantic_pnf_scope_class",
        "semantic_pnf_demand_constraint",
        "semantic_pnf_actor_profile",
        "semantic_pnf_frontier_outcome",
        "semantic_pnf_frontier_resolution",
        "semantic_pnf_frontier_reduction_receipt",
        "semantic_pnf_frontier_stage_receipt",
        "origin_interface_id",
        "outward_required",
    ):
        assert required in source


def test_parent_frontier_is_rebuilt_set_wise_and_not_copied_wholesale() -> None:
    source = _source()
    start = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.rebuild_numeric_pnf_parent_frontier"
    )
    end = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.reduce_numeric_pnf_interface_on_close",
        start,
    )
    function_source = source[start:end]

    assert "semantic_pnf_actor_profile" in function_source
    assert "semantic_pnf_frontier_resolution" in function_source
    assert "child_export.target_kind = 3" in function_source
    assert "child_export.target_kind = 1" in function_source
    assert "factor.support_score" in function_source
    assert "HAVING count(*) = 1" in function_source
    assert "resolved_target_id" in function_source
    assert "state = 3" in function_source

    # The prior implementation copied every child export and lookup row into
    # the parent. The sparse function must admit parent rows through explicit
    # target-family branches instead.
    assert (
        "SELECT selected_interface_id,\n"
        "           child_export.export_kind,\n"
        "           child_export.target_kind,\n"
        "           child_export.target_id"
    ) in function_source
    assert "WHERE child_export.target_kind IN (4, 5)" in function_source
    assert "JOIN execution.semantic_pnf_interface_export AS parent_export" in (
        function_source
    )


def test_hidden_document_wide_planning_triggers_are_removed() -> None:
    source = _source()
    for trigger_name in (
        "semantic_pnf_global_demand_planning",
        "semantic_pnf_visible_demand_planning",
    ):
        assert f"DROP TRIGGER IF EXISTS {trigger_name}" in source
    assert "CREATE TRIGGER semantic_pnf_global_demand_planning" not in source
    assert "CREATE TRIGGER semantic_pnf_visible_demand_planning" not in source


def test_frontier_reduction_runs_at_region_closure() -> None:
    source = _source()
    for required in (
        "reduce_numeric_pnf_interface_on_close",
        "semantic_pnf_sparse_frontier_on_close",
        "AFTER UPDATE OF closure_state",
        "rebuild_numeric_pnf_parent_frontier",
    ):
        assert required in source


def test_global_lookup_is_root_only_and_incremental() -> None:
    source = _source()
    start = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_pnf_global_lookup_ids"
    )
    end = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_pnf_visible_lookup",
        start,
    )
    function_source = source[start:end]

    assert "region.region_kind = 10" in function_source
    assert "root_interface_id" in function_source
    assert "global.interface_id <> root_interface_id" in function_source
    assert "lookup.interface_id = root_interface_id" in function_source
    assert "ON CONFLICT (" in function_source
    assert "DO UPDATE SET" in function_source


def test_visible_projection_contains_only_the_closed_root_frontier() -> None:
    source = _source()
    start = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.refresh_pnf_visible_lookup"
    )
    end = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.plan_numeric_pnf_demand_candidates_ids",
        start,
    )
    function_source = source[start:end]

    assert "reduce_numeric_pnf_document_frontiers" in function_source
    assert "lookup.interface_id = root_interface_id" in function_source
    assert "root_interface_id,\n               0," in function_source
    assert "WITH RECURSIVE chain" not in function_source
    assert "JOIN execution.semantic_pnf_interface_ancestor" not in function_source


def test_compatibility_planner_no_longer_scans_global_inventory() -> None:
    source = _source()
    start = source.index(
        "CREATE OR REPLACE FUNCTION "
        "execution.plan_numeric_pnf_demand_candidates_ids"
    )
    function_source = source[start:]
    assert "reduce_numeric_pnf_document_frontiers" in function_source
    assert "semantic_pnf_global_lookup" not in function_source
    assert "FOR demand_row IN" not in function_source
    assert "LEFT JOIN LATERAL" not in function_source


def test_actor_profile_uses_one_numeric_unspecified_value() -> None:
    source = ACTOR_NORMALISATION.read_text(encoding="utf-8")
    for required in (
        "normalize_numeric_pnf_actor_profile_key",
        "COALESCE(NEW.object_kind_symbol_id, 0)",
        "COALESCE(NEW.role_symbol_id, 0)",
        "COALESCE(NEW.factor_type_symbol_id",
        "COALESCE(NEW.predicate_symbol_id, 0)",
        "semantic_pnf_actor_profile_key_normalisation",
    ):
        assert required in source


def test_anaphor_surface_is_not_an_identity_constraint() -> None:
    source = ANAPHOR_SURFACE.read_text(encoding="utf-8")
    for required in (
        "surface_lexical_symbol_id",
        "normalize_numeric_pnf_anaphor_surface",
        "symbol_text = 'anaphor_unresolved'",
        "NEW.surface_lexical_symbol_id := COALESCE",
        "NEW.lexical_symbol_id := NULL",
        "semantic_pnf_anaphor_surface_normalisation",
        "DELETE FROM execution.semantic_pnf_interface_lookup",
    ):
        assert required in source
