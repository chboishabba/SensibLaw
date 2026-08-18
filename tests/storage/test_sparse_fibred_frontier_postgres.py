from __future__ import annotations

import os

import pytest

from src.storage.postgres.spacy_parser_model import connect


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL schema checks",
)


def _fetch_names(query: str) -> set[str]:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return {str(row[0]) for row in cursor.fetchall()}
    finally:
        connection.close()


def test_sparse_frontier_schema_objects_are_installed() -> None:
    names = _fetch_names(
        """
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = 'execution'
           AND table_name LIKE 'semantic_pnf_%'
        """
    )
    assert {
        "semantic_pnf_scope_class",
        "semantic_pnf_demand_constraint",
        "semantic_pnf_actor_profile",
        "semantic_pnf_frontier_outcome",
        "semantic_pnf_frontier_resolution",
        "semantic_pnf_frontier_reduction_receipt",
        "semantic_pnf_frontier_stage_receipt",
        "semantic_pnf_frontier_dirty",
    } <= names


def test_sparse_frontier_functions_are_installed() -> None:
    names = _fetch_names(
        """
        SELECT routine_name
          FROM information_schema.routines
         WHERE routine_schema = 'execution'
        """
    )
    assert {
        "refresh_numeric_pnf_demand_constraints",
        "normalize_numeric_pnf_actor_profile_key",
        "normalize_numeric_pnf_anaphor_surface",
        "capture_numeric_pnf_actor_export_profiles",
        "filter_numeric_pnf_candidate_constraints",
        "index_numeric_pnf_object_exports_batch",
        "rebuild_numeric_pnf_parent_frontier",
        "rebuild_numeric_pnf_parent_frontier_canonical",
        "enqueue_numeric_pnf_parent_frontier",
        "reduce_numeric_pnf_interface_on_close",
        "reduce_numeric_pnf_document_frontiers",
        "refresh_pnf_global_lookup_ids",
        "refresh_pnf_visible_lookup",
        "plan_numeric_pnf_demand_candidates_ids",
    } <= names


def test_sparse_dirty_closure_functions_preserve_current_topology() -> None:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT procedure.proname, pg_get_functiondef(procedure.oid)
                  FROM pg_proc AS procedure
                  JOIN pg_namespace AS namespace
                    ON namespace.oid = procedure.pronamespace
                 WHERE namespace.nspname = 'execution'
                   AND procedure.proname IN (
                       'rebuild_numeric_pnf_parent_frontier',
                       'reduce_numeric_pnf_interface_on_close',
                       'reduce_numeric_pnf_document_frontiers'
                   )
                """
            )
            definitions = {str(name): str(source) for name, source in cursor.fetchall()}
    finally:
        connection.close()

    assert (
        "selected_kind IN (2, 4, 9)"
        in definitions["rebuild_numeric_pnf_parent_frontier"]
    )
    assert (
        "NEW.region_kind IN (2, 4, 9)"
        in definitions["reduce_numeric_pnf_interface_on_close"]
    )
    assert (
        "semantic_pnf_frontier_dirty"
        in definitions["reduce_numeric_pnf_document_frontiers"]
    )


def test_hidden_and_row_wise_planning_triggers_are_absent() -> None:
    names = _fetch_names(
        """
        SELECT trigger_name
          FROM information_schema.triggers
         WHERE trigger_schema = 'execution'
        """
    )
    assert "semantic_pnf_global_demand_planning" not in names
    assert "semantic_pnf_visible_demand_planning" not in names
    assert "semantic_pnf_object_export_kind_index" not in names
    assert "semantic_pnf_sparse_frontier_on_close" in names
    assert "semantic_pnf_actor_profile_key_normalisation" in names
    assert "semantic_pnf_anaphor_surface_normalisation" in names
    assert "semantic_pnf_actor_export_profile" in names
    assert "semantic_pnf_typed_candidate_constraints" in names
    assert "semantic_pnf_object_export_kind_index_batch" in names


def test_global_lookup_function_is_root_frontier_only() -> None:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_functiondef(procedure.oid)
                  FROM pg_proc AS procedure
                  JOIN pg_namespace AS namespace
                    ON namespace.oid = procedure.pronamespace
                 WHERE namespace.nspname = 'execution'
                   AND procedure.proname = 'refresh_pnf_global_lookup_ids'
                   AND pg_get_function_identity_arguments(procedure.oid)
                       = 'selected_run_id bigint, selected_document_id bigint'
                """
            )
            row = cursor.fetchone()
            assert row is not None
            source = str(row[0])
    finally:
        connection.close()

    assert "region.region_kind = 10" in source
    assert "lookup.interface_id = root_interface_id" in source
    assert "global.interface_id <> root_interface_id" in source


def test_actor_profile_unspecified_dimensions_are_numeric() -> None:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, column_default, is_nullable
                  FROM information_schema.columns
                 WHERE table_schema = 'execution'
                   AND table_name = 'semantic_pnf_actor_profile'
                   AND column_name IN (
                       'object_kind_symbol_id',
                       'role_symbol_id',
                       'factor_type_symbol_id',
                       'predicate_symbol_id'
                   )
                """
            )
            rows = tuple(cursor.fetchall())
    finally:
        connection.close()

    assert len(rows) == 4
    assert all(str(default) == "0" for _, default, _ in rows)
    assert all(str(nullable) == "NO" for _, _, nullable in rows)


def test_actor_profile_nonzero_dimensions_have_fk_projections() -> None:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, is_generated, generation_expression
                  FROM information_schema.columns
                 WHERE table_schema = 'execution'
                   AND table_name = 'semantic_pnf_actor_profile'
                   AND column_name IN (
                       'object_kind_symbol_fk',
                       'role_symbol_fk',
                       'factor_type_symbol_fk',
                       'predicate_symbol_fk'
                   )
                """
            )
            rows = tuple(cursor.fetchall())
    finally:
        connection.close()

    assert len(rows) == 4
    assert all(str(generated) == "ALWAYS" for _, generated, _ in rows)
    assert all("nullif" in str(expression).casefold() for _, _, expression in rows)


def test_anaphor_surface_column_is_installed() -> None:
    assert DATABASE_URL is not None
    connection = connect(DATABASE_URL)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT is_nullable
                  FROM information_schema.columns
                 WHERE table_schema = 'execution'
                   AND table_name = 'semantic_pnf_demand'
                   AND column_name = 'surface_lexical_symbol_id'
                """
            )
            row = cursor.fetchone()
    finally:
        connection.close()
    assert row is not None
    assert str(row[0]) == "YES"
