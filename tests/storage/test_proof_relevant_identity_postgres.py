from __future__ import annotations

import os

import pytest

from src.storage.postgres.spacy_parser_model import connect


DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL is required for PostgreSQL schema checks",
)


def _names(query: str) -> set[str]:
    assert DATABASE_URL is not None
    with connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return {str(row[0]) for row in cursor.fetchall()}


def _function_source(name: str, identity_arguments: str) -> str:
    assert DATABASE_URL is not None
    with connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_functiondef(procedure.oid)
                  FROM pg_proc AS procedure
                  JOIN pg_namespace AS namespace
                    ON namespace.oid = procedure.pronamespace
                 WHERE namespace.nspname = 'execution'
                   AND procedure.proname = %s
                   AND pg_get_function_identity_arguments(procedure.oid) = %s
                """,
                (name, identity_arguments),
            )
            row = cursor.fetchone()
    assert row is not None
    return str(row[0])


def test_proof_relevant_identity_and_derivation_tables_are_installed() -> None:
    names = _names(
        """
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema = 'execution'
        """
    )
    assert {
        "semantic_pnf_identity_authority_class",
        "semantic_pnf_identity_witness_kind",
        "semantic_pnf_identity_admission_state",
        "semantic_pnf_canonical_entity",
        "semantic_pnf_identity_witness",
        "semantic_pnf_identity_witness_admission",
        "semantic_pnf_identity_witness_constraint",
        "semantic_pnf_derivation_state",
        "semantic_pnf_derivation_kind",
        "semantic_pnf_factor_derivation_rule",
        "semantic_pnf_factor_derivation",
        "semantic_pnf_factor_derivation_premise",
        "semantic_pnf_factor_derivation_argument",
        "semantic_pnf_factor_composition_candidate",
    } <= names


def test_proof_relevant_views_are_installed() -> None:
    names = _names(
        """
        SELECT table_name
          FROM information_schema.views
         WHERE table_schema = 'execution'
        """
    )
    assert {
        "semantic_pnf_identity_projection",
        "semantic_pnf_identity_fibre_member",
        "semantic_pnf_witnessed_hyperedge",
    } <= names


def test_proof_relevant_functions_are_installed() -> None:
    names = _names(
        """
        SELECT routine_name
          FROM information_schema.routines
         WHERE routine_schema = 'execution'
        """
    )
    assert {
        "refresh_numeric_pnf_demand_source_objects",
        "refresh_numeric_pnf_identity_witnesses",
        "refresh_numeric_pnf_identity_substitution_derivations",
        "refresh_numeric_pnf_factor_composition_candidates",
        "refresh_numeric_pnf_semantic_derivations",
        "admit_numeric_pnf_external_identity_alignment",
        "retract_numeric_pnf_identity_witness",
        "validate_numeric_pnf_identity_admission",
    } <= names


def test_world_canonical_flag_is_reserved_for_external_authority() -> None:
    assert DATABASE_URL is not None
    with connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT authority_name, world_canonical
                  FROM execution.semantic_pnf_identity_authority_class
                 ORDER BY authority_class
                """
            )
            rows = tuple(cursor.fetchall())
    assert rows == (
        ("surface_local", False),
        ("document_derived", False),
        ("corpus_derived", False),
        ("external_authority", True),
    )


def test_root_lookup_definition_is_sparse_after_performance_migration() -> None:
    source = _function_source(
        "refresh_pnf_global_lookup_ids",
        "selected_run_id bigint, selected_document_id bigint",
    )
    assert "region.region_kind = 10" in source
    assert "lookup.interface_id = root_interface_id" in source
    assert "global.interface_id <> root_interface_id" in source


def test_planner_definition_is_history_independent_sparse_reduction() -> None:
    source = _function_source(
        "plan_numeric_pnf_demand_candidates_ids",
        "selected_run_id bigint, selected_document_id bigint",
    )
    assert "reduce_numeric_pnf_document_frontiers" in source
    assert "semantic_pnf_global_lookup" not in source
    assert "LATERAL" not in source


def test_identity_projection_requires_accepted_unique_matching_authority() -> None:
    assert DATABASE_URL is not None
    with connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_viewdef(
                    'execution.semantic_pnf_identity_projection'::regclass,
                    true
                )
                """
            )
            row = cursor.fetchone()
    assert row is not None
    source = str(row[0]).casefold()
    assert "admission_state = 2" in source
    assert "candidate_count = 1" in source
    assert "entity.authority_class = witness.authority_class" in source
    assert "count(distinct witness.target_entity_id) = 1" in source


def test_identity_admission_integrity_trigger_is_installed() -> None:
    names = _names(
        """
        SELECT trigger_name
          FROM information_schema.triggers
         WHERE trigger_schema = 'execution'
        """
    )
    assert "semantic_pnf_identity_admission_integrity" in names
    source = _function_source(
        "validate_numeric_pnf_identity_admission",
        "",
    )
    assert "witness_candidate_count <> 1" in source
    assert "witness_authority_class <> entity_authority_class" in source


def test_external_alignment_function_has_no_discovery_surface() -> None:
    source = _function_source(
        "admit_numeric_pnf_external_identity_alignment",
        "selected_source_object_id bigint, selected_authority_namespace text, "
        "selected_authority_identifier text, selected_canonical_symbol_id bigint, "
        "selected_source_interface_id bigint",
    ).casefold()
    assert "authority_namespace" in source
    assert "authority_identifier" in source
    assert "semantic_pnf_identity_witness" in source
    assert (
        "decode('00'::text, 'hex'::text)" in source or "decode('00', 'hex')" in source
    )
    assert "paragraph" not in source
    assert "similarity" not in source
    assert "semantic_pnf_global_lookup" not in source


def test_external_alignment_and_retraction_refresh_current_derived_surface() -> None:
    admit = _function_source(
        "admit_numeric_pnf_external_identity_alignment",
        "selected_source_object_id bigint, selected_authority_namespace text, "
        "selected_authority_identifier text, selected_canonical_symbol_id bigint, "
        "selected_source_interface_id bigint",
    )
    retract = _function_source(
        "retract_numeric_pnf_identity_witness",
        "selected_witness_id bigint",
    )
    for source in (admit, retract):
        assert "refresh_numeric_pnf_identity_substitution_derivations" in source
        assert "refresh_numeric_pnf_factor_composition_candidates" in source
