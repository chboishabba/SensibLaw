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
                   AND procedure.proname = 'refresh_pnf_global_lookup_ids'
                   AND pg_get_function_identity_arguments(procedure.oid)
                       = 'selected_run_id bigint, selected_document_id bigint'
                """
            )
            row = cursor.fetchone()
    assert row is not None
    source = str(row[0])
    assert "region.region_kind = 10" in source
    assert "lookup.interface_id = root_interface_id" in source
    assert "global.interface_id <> root_interface_id" in source


def test_identity_projection_requires_accepted_unambiguous_target() -> None:
    assert DATABASE_URL is not None
    with connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_viewdef('execution.semantic_pnf_identity_projection'::regclass, true)
                """
            )
            row = cursor.fetchone()
    assert row is not None
    source = str(row[0]).casefold()
    assert "admission_state = 2" in source
    assert "count(distinct witness.target_entity_id) = 1" in source
