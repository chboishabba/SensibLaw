#!/usr/bin/env python3
"""E0d old-vs-new authority parity and execution-geometry certification.

Compare a migration-179 replay with a migration-180 replay using portable
semantic coordinates. Database-local BIGINT allocation and PNF digests whose
preimages contain such allocation are deliberately excluded from the hard gate.

Optional replay commands are executed under PostgreSQL PL/pgSQL function
accounting. Semantic parity is a hard gate; performance is evidence only.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from time import monotonic_ns
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.storage.postgres.delta_projection_certification import (
    DeltaCertificationLayer,
    certify_layers,
)
from src.storage.postgres.spacy_parser_model import connect

CONTRACT = "sensiblaw.e0d-anaphor-delta-certification.v0_2"

LAYERS = (
    DeltaCertificationLayer("source_delta", ("source_pronouns",)),
    DeltaCertificationLayer(
        "projection_atoms",
        (
            "mentions",
            "mention_token_support",
            "object_token_support",
            "object_mention_support",
        ),
    ),
    DeltaCertificationLayer("affected_keys", ("affected_interfaces",)),
    DeltaCertificationLayer("demand_authority", ("demands",)),
    DeltaCertificationLayer(
        "derived_surfaces",
        ("demand_exports", "demand_lookups", "occurrence_provenance"),
    ),
    DeltaCertificationLayer(
        "candidate_authority",
        ("candidates", "frontier_resolutions"),
    ),
    DeltaCertificationLayer(
        "authority_publication",
        ("affected_interface_authority", "document_authority"),
    ),
)

_SCOPE = """
source_region.run_ref=%s
AND (%s IS NULL OR source_region.document_ref=%s)
"""

_DEMAND_CTE = """
WITH scoped_demand AS MATERIALIZED (
    SELECT demand.*,
           source_region.region_kind AS source_region_kind,
           source_region.start_char AS source_region_start,
           source_region.end_char AS source_region_end,
           source_token.start_char AS source_token_start,
           source_token.end_char AS source_token_end,
           source_token.local_token_ordinal AS source_token_ordinal,
           encode(source_token.token_digest,'hex') AS source_token_digest,
           encode(source_kind.symbol_digest,'hex') AS source_kind_digest,
           encode(source_head.symbol_digest,'hex') AS source_head_digest,
           encode(expected_factor.symbol_digest,'hex') AS expected_factor_digest,
           encode(expected_object.symbol_digest,'hex') AS expected_object_digest,
           encode(lexical.symbol_digest,'hex') AS lexical_digest,
           encode(surface.symbol_digest,'hex') AS surface_digest,
           encode(role.symbol_digest,'hex') AS role_digest,
           encode(residual.symbol_digest,'hex') AS residual_digest
      FROM execution.semantic_pnf_demand AS demand
      JOIN execution.semantic_pnf_region AS source_region
        ON source_region.region_id=demand.source_region_id
      JOIN execution.semantic_symbol AS residual
        ON residual.symbol_id=demand.residual_type_symbol_id
       AND residual.kind_id=13
       AND residual.symbol_text='anaphor_unresolved'
      LEFT JOIN execution.semantic_pnf_object AS source_object
        ON source_object.object_id=demand.source_object_id
      LEFT JOIN execution.semantic_symbol AS source_kind
        ON source_kind.symbol_id=source_object.object_kind_symbol_id
      LEFT JOIN execution.semantic_symbol AS source_head
        ON source_head.symbol_id=source_object.head_symbol_id
      LEFT JOIN execution.semantic_pnf_object_token_support AS source_support
        ON source_support.object_id=source_object.object_id
       AND source_support.ordinal=0
      LEFT JOIN execution.semantic_parser_token AS source_token
        ON source_token.token_id=source_support.token_id
      LEFT JOIN execution.semantic_symbol AS expected_factor
        ON expected_factor.symbol_id=demand.expected_factor_type_symbol_id
      LEFT JOIN execution.semantic_symbol AS expected_object
        ON expected_object.symbol_id=demand.expected_object_kind_symbol_id
      LEFT JOIN execution.semantic_symbol AS lexical
        ON lexical.symbol_id=demand.lexical_symbol_id
      LEFT JOIN execution.semantic_symbol AS surface
        ON surface.symbol_id=demand.surface_lexical_symbol_id
      LEFT JOIN execution.semantic_symbol AS role
        ON role.symbol_id=demand.role_symbol_id
     WHERE """ + _SCOPE + """
)
"""

_DEMAND_KEY = """
d.source_region_kind,
d.source_region_start,
d.source_region_end,
d.source_token_start,
d.source_token_end,
d.source_token_ordinal,
d.source_kind_digest,
d.source_head_digest,
d.surface_digest,
d.residual_digest
"""


def _rows(cursor: Any, query: str, params: tuple[Any, ...]) -> tuple[tuple[Any, ...], ...]:
    cursor.execute(query, params)
    return tuple(tuple(row) for row in cursor.fetchall())


def _scope_params(run_ref: str, document_ref: str | None) -> tuple[Any, ...]:
    return (run_ref, document_ref, document_ref)


def _object_target_sql(prefix: str) -> str:
    return f"""
    concat_ws(':',
        'object',
        {prefix}_region.region_kind::TEXT,
        {prefix}_region.start_char::TEXT,
        {prefix}_region.end_char::TEXT,
        encode({prefix}_kind.symbol_digest,'hex'),
        encode({prefix}_head.symbol_digest,'hex'),
        COALESCE((
            SELECT string_agg(
                       token.start_char::TEXT || '-' || token.end_char::TEXT,
                       ',' ORDER BY support.ordinal,token.start_char,token.end_char
                   )
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_parser_token AS token
                ON token.token_id=support.token_id
             WHERE support.object_id={prefix}.object_id
        ),'')
    )
    """


def _factor_target_sql(prefix: str) -> str:
    return f"""
    concat_ws(':',
        'factor',
        {prefix}_region.region_kind::TEXT,
        {prefix}_region.start_char::TEXT,
        {prefix}_region.end_char::TEXT,
        encode({prefix}_type.symbol_digest,'hex'),
        encode({prefix}_predicate.symbol_digest,'hex'),
        COALESCE((
            SELECT string_agg(
                       token.start_char::TEXT || '-' || token.end_char::TEXT,
                       ',' ORDER BY support.ordinal,token.start_char,token.end_char
                   )
              FROM execution.semantic_pnf_factor_token_support AS support
              JOIN execution.semantic_parser_token AS token
                ON token.token_id=support.token_id
             WHERE support.factor_id={prefix}.factor_id
        ),'')
    )
    """


def _snapshot(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str | None,
) -> dict[str, tuple[tuple[Any, ...], ...]]:
    connection = connect(database_url)
    scope = _scope_params(run_ref, document_ref)
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")

                source_pronouns = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           token.start_char,
                           token.end_char,
                           token.local_token_ordinal,
                           encode(lemma.symbol_digest,'hex'),
                           encode(pos.symbol_digest,'hex')
                      FROM execution.semantic_pnf_region AS source_region
                      JOIN execution.semantic_pnf_sentence_region AS mapping
                        ON mapping.region_id=source_region.region_id
                      JOIN execution.semantic_parser_token AS token
                        ON token.sentence_id=mapping.sentence_id
                       AND token.representation_version=2
                      JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
                        ON constant.singleton
                       AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
                      JOIN execution.semantic_symbol AS lemma
                        ON lemma.symbol_id=token.lemma_symbol_id
                      JOIN execution.semantic_symbol AS pos
                        ON pos.symbol_id=token.pos_symbol_id
                     WHERE """ + _SCOPE + """
                     ORDER BY source_region.start_char,token.start_char,
                              token.local_token_ordinal
                    """,
                    scope,
                )

                mentions = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           mention.start_char,
                           mention.end_char,
                           mention.mention_kind,
                           token.start_char,
                           token.end_char,
                           token.local_token_ordinal,
                           encode(head.symbol_digest,'hex'),
                           encode(object_kind.symbol_digest,'hex'),
                           encode(object_head.symbol_digest,'hex')
                      FROM execution.semantic_pnf_mention AS mention
                      JOIN execution.semantic_pnf_region AS source_region
                        ON source_region.region_id=mention.region_id
                      JOIN execution.semantic_parser_token AS token
                        ON token.token_id=mention.head_token_id
                      JOIN execution.semantic_symbol AS head
                        ON head.symbol_id=mention.head_symbol_id
                      LEFT JOIN execution.semantic_pnf_object AS object
                        ON object.object_id=mention.object_id
                      LEFT JOIN execution.semantic_symbol AS object_kind
                        ON object_kind.symbol_id=object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS object_head
                        ON object_head.symbol_id=object.head_symbol_id
                     WHERE """ + _SCOPE + """
                       AND mention.mention_kind=4
                     ORDER BY source_region.start_char,mention.start_char,
                              token.local_token_ordinal
                    """,
                    scope,
                )

                mention_token_support = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           mention.start_char,
                           mention.end_char,
                           mention.mention_kind,
                           token.start_char,
                           token.end_char,
                           token.local_token_ordinal,
                           support.ordinal
                      FROM execution.semantic_pnf_mention AS mention
                      JOIN execution.semantic_pnf_region AS source_region
                        ON source_region.region_id=mention.region_id
                      JOIN execution.semantic_pnf_mention_token AS support
                        ON support.mention_id=mention.mention_id
                      JOIN execution.semantic_parser_token AS token
                        ON token.token_id=support.token_id
                     WHERE """ + _SCOPE + """
                       AND mention.mention_kind=4
                     ORDER BY source_region.start_char,mention.start_char,
                              support.ordinal,token.local_token_ordinal
                    """,
                    scope,
                )

                object_token_support = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           encode(object_kind.symbol_digest,'hex'),
                           encode(object_head.symbol_digest,'hex'),
                           token.start_char,
                           token.end_char,
                           token.local_token_ordinal,
                           support.ordinal
                      FROM execution.semantic_pnf_mention AS mention
                      JOIN execution.semantic_pnf_region AS source_region
                        ON source_region.region_id=mention.region_id
                      JOIN execution.semantic_pnf_object AS object
                        ON object.object_id=mention.object_id
                      JOIN execution.semantic_symbol AS object_kind
                        ON object_kind.symbol_id=object.object_kind_symbol_id
                      JOIN execution.semantic_symbol AS object_head
                        ON object_head.symbol_id=object.head_symbol_id
                      JOIN execution.semantic_pnf_object_token_support AS support
                        ON support.object_id=object.object_id
                      JOIN execution.semantic_parser_token AS token
                        ON token.token_id=support.token_id
                     WHERE """ + _SCOPE + """
                       AND mention.mention_kind=4
                     ORDER BY source_region.start_char,token.start_char,support.ordinal
                    """,
                    scope,
                )

                object_mention_support = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           encode(object_kind.symbol_digest,'hex'),
                           encode(object_head.symbol_digest,'hex'),
                           mention.start_char,
                           mention.end_char,
                           mention.mention_kind
                      FROM execution.semantic_pnf_mention AS mention
                      JOIN execution.semantic_pnf_region AS source_region
                        ON source_region.region_id=mention.region_id
                      JOIN execution.semantic_pnf_object AS object
                        ON object.object_id=mention.object_id
                      JOIN execution.semantic_symbol AS object_kind
                        ON object_kind.symbol_id=object.object_kind_symbol_id
                      JOIN execution.semantic_symbol AS object_head
                        ON object_head.symbol_id=object.head_symbol_id
                      JOIN execution.semantic_pnf_object_mention_support AS support
                        ON support.object_id=object.object_id
                       AND support.mention_id=mention.mention_id
                     WHERE """ + _SCOPE + """
                       AND mention.mention_kind=4
                     ORDER BY source_region.start_char,mention.start_char
                    """,
                    scope,
                )

                demands = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    SELECT """ + _DEMAND_KEY + """,
                           d.expected_target_kind,
                           d.expected_factor_digest,
                           d.expected_object_digest,
                           d.lexical_digest,
                           d.role_digest,
                           d.recency_class,
                           d.state,
                           d.max_candidates,
                           d.source_start_char,
                           d.candidate_count,
                           d.resolved_target_kind
                      FROM scoped_demand AS d
                     ORDER BY d.source_region_start,d.source_token_start,
                              d.source_token_ordinal,d.residual_digest
                    """,
                    scope,
                )

                demand_exports = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    SELECT """ + _DEMAND_KEY + """,
                           interface_region.region_kind,
                           interface_region.start_char,
                           interface_region.end_char,
                           export.export_kind,
                           export.target_kind,
                           encode(key_symbol.symbol_digest,'hex'),
                           encode(role_symbol.symbol_digest,'hex'),
                           encode(residual_symbol.symbol_digest,'hex'),
                           row_number() OVER (
                               PARTITION BY interface_region.region_kind,
                                            interface_region.start_char,
                                            interface_region.end_char
                               ORDER BY d.source_token_start,d.source_token_end,
                                        d.source_token_ordinal,d.residual_digest
                           )::BIGINT,
                           export.promotion_score
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_interface_export AS export
                        ON export.target_kind=3
                       AND export.target_id=d.demand_id
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=export.interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                      LEFT JOIN execution.semantic_symbol AS key_symbol
                        ON key_symbol.symbol_id=export.key_symbol_id
                      LEFT JOIN execution.semantic_symbol AS role_symbol
                        ON role_symbol.symbol_id=export.role_symbol_id
                      LEFT JOIN execution.semantic_symbol AS residual_symbol
                        ON residual_symbol.symbol_id=export.residual_type_symbol_id
                     ORDER BY interface_region.start_char,d.source_token_start
                    """,
                    scope,
                )

                demand_lookups = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    SELECT """ + _DEMAND_KEY + """,
                           interface_region.region_kind,
                           interface_region.start_char,
                           interface_region.end_char,
                           lookup.key_kind,
                           CASE WHEN lookup.key_a=0 THEN '0'
                                ELSE encode(key_a.symbol_digest,'hex') END,
                           CASE WHEN lookup.key_b=0 THEN '0'
                                ELSE encode(key_b.symbol_digest,'hex') END,
                           lookup.target_kind,
                           row_number() OVER (
                               PARTITION BY interface_region.region_kind,
                                            interface_region.start_char,
                                            interface_region.end_char,
                                            lookup.key_kind
                               ORDER BY d.source_token_start,d.source_token_end,
                                        d.source_token_ordinal,d.residual_digest
                           )::BIGINT
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_interface_lookup AS lookup
                        ON lookup.target_kind=3
                       AND lookup.target_id=d.demand_id
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=lookup.interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                      LEFT JOIN execution.semantic_symbol AS key_a
                        ON key_a.symbol_id=lookup.key_a
                      LEFT JOIN execution.semantic_symbol AS key_b
                        ON key_b.symbol_id=lookup.key_b
                     ORDER BY interface_region.start_char,lookup.key_kind,
                              d.source_token_start
                    """,
                    scope,
                )

                occurrence_provenance = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    SELECT """ + _DEMAND_KEY + """,
                           provenance.occurrence_role,
                           token.start_char,
                           token.end_char,
                           token.local_token_ordinal,
                           object_region.region_kind,
                           object_region.start_char,
                           object_region.end_char,
                           encode(object_kind.symbol_digest,'hex'),
                           encode(object_head.symbol_digest,'hex'),
                           provenance.ordinal,
                           provenance.producer_ref
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_demand_occurrence_provenance AS provenance
                        ON provenance.demand_id=d.demand_id
                      JOIN execution.semantic_parser_token AS token
                        ON token.token_id=provenance.token_id
                      LEFT JOIN execution.semantic_pnf_object AS object
                        ON object.object_id=provenance.object_id
                      LEFT JOIN execution.semantic_pnf_region AS object_region
                        ON object_region.region_id=object.region_id
                      LEFT JOIN execution.semantic_symbol AS object_kind
                        ON object_kind.symbol_id=object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS object_head
                        ON object_head.symbol_id=object.head_symbol_id
                     ORDER BY d.source_region_start,d.source_token_start,
                              provenance.occurrence_role,provenance.ordinal
                    """,
                    scope,
                )

                object_target = _object_target_sql("target_object")
                factor_target = _factor_target_sql("target_factor")
                candidates = _rows(
                    cursor,
                    _DEMAND_CTE + f"""
                    SELECT {_DEMAND_KEY},
                           candidate.ordinal,
                           candidate.target_kind,
                           CASE candidate.target_kind
                             WHEN 1 THEN {object_target}
                             WHEN 2 THEN {factor_target}
                             ELSE concat_ws(
                                 ':','demand',
                                 target_demand_region.region_kind::TEXT,
                                 target_demand_region.start_char::TEXT,
                                 target_demand_region.end_char::TEXT,
                                 target_demand_token.start_char::TEXT,
                                 target_demand_token.end_char::TEXT,
                                 encode(target_demand_residual.symbol_digest,'hex')
                             )
                           END,
                           source_interface_region.region_kind,
                           source_interface_region.start_char,
                           source_interface_region.end_char,
                           candidate.ancestor_distance,
                           candidate.index_rank,
                           candidate.candidate_score,
                           common_scope_region.region_kind,
                           common_scope_region.start_char,
                           common_scope_region.end_char,
                           candidate.validation_state
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_demand_candidate AS candidate
                        ON candidate.demand_id=d.demand_id
                      LEFT JOIN execution.semantic_pnf_object AS target_object
                        ON candidate.target_kind=1
                       AND target_object.object_id=candidate.target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_object_region
                        ON target_object_region.region_id=target_object.region_id
                      LEFT JOIN execution.semantic_symbol AS target_object_kind
                        ON target_object_kind.symbol_id=target_object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS target_object_head
                        ON target_object_head.symbol_id=target_object.head_symbol_id
                      LEFT JOIN execution.semantic_pnf_factor AS target_factor
                        ON candidate.target_kind=2
                       AND target_factor.factor_id=candidate.target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_factor_region
                        ON target_factor_region.region_id=target_factor.region_id
                      LEFT JOIN execution.semantic_symbol AS target_factor_type
                        ON target_factor_type.symbol_id=target_factor.factor_type_symbol_id
                      LEFT JOIN execution.semantic_symbol AS target_factor_predicate
                        ON target_factor_predicate.symbol_id=target_factor.predicate_symbol_id
                      LEFT JOIN execution.semantic_pnf_demand AS target_demand
                        ON candidate.target_kind=3
                       AND target_demand.demand_id=candidate.target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_demand_region
                        ON target_demand_region.region_id=target_demand.source_region_id
                      LEFT JOIN execution.semantic_symbol AS target_demand_residual
                        ON target_demand_residual.symbol_id=target_demand.residual_type_symbol_id
                      LEFT JOIN execution.semantic_pnf_object_token_support AS target_demand_support
                        ON target_demand_support.object_id=target_demand.source_object_id
                       AND target_demand_support.ordinal=0
                      LEFT JOIN execution.semantic_parser_token AS target_demand_token
                        ON target_demand_token.token_id=target_demand_support.token_id
                      LEFT JOIN execution.semantic_pnf_interface AS source_interface
                        ON source_interface.interface_id=candidate.source_interface_id
                      LEFT JOIN execution.semantic_pnf_region AS source_interface_region
                        ON source_interface_region.region_id=source_interface.region_id
                      LEFT JOIN execution.semantic_pnf_interface AS common_scope
                        ON common_scope.interface_id=candidate.common_scope_interface_id
                      LEFT JOIN execution.semantic_pnf_region AS common_scope_region
                        ON common_scope_region.region_id=common_scope.region_id
                     ORDER BY d.source_region_start,d.source_token_start,
                              candidate.ordinal,candidate.target_kind
                    """,
                    scope,
                )

                frontier_resolutions = _rows(
                    cursor,
                    _DEMAND_CTE + f"""
                    SELECT {_DEMAND_KEY},
                           interface_region.region_kind,
                           interface_region.start_char,
                           interface_region.end_char,
                           resolution.outcome_state,
                           resolution.candidate_count,
                           resolution.selected_target_kind,
                           CASE resolution.selected_target_kind
                             WHEN 1 THEN {object_target}
                             WHEN 2 THEN {factor_target}
                             WHEN 3 THEN concat_ws(
                                 ':','demand',
                                 target_demand_region.region_kind::TEXT,
                                 target_demand_region.start_char::TEXT,
                                 target_demand_region.end_char::TEXT,
                                 target_demand_token.start_char::TEXT,
                                 target_demand_token.end_char::TEXT,
                                 encode(target_demand_residual.symbol_digest,'hex')
                             )
                             ELSE NULL
                           END,
                           witness_region.region_kind,
                           witness_region.start_char,
                           witness_region.end_char
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_frontier_resolution AS resolution
                        ON resolution.demand_id=d.demand_id
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=resolution.interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                      LEFT JOIN execution.semantic_pnf_object AS target_object
                        ON resolution.selected_target_kind=1
                       AND target_object.object_id=resolution.selected_target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_object_region
                        ON target_object_region.region_id=target_object.region_id
                      LEFT JOIN execution.semantic_symbol AS target_object_kind
                        ON target_object_kind.symbol_id=target_object.object_kind_symbol_id
                      LEFT JOIN execution.semantic_symbol AS target_object_head
                        ON target_object_head.symbol_id=target_object.head_symbol_id
                      LEFT JOIN execution.semantic_pnf_factor AS target_factor
                        ON resolution.selected_target_kind=2
                       AND target_factor.factor_id=resolution.selected_target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_factor_region
                        ON target_factor_region.region_id=target_factor.region_id
                      LEFT JOIN execution.semantic_symbol AS target_factor_type
                        ON target_factor_type.symbol_id=target_factor.factor_type_symbol_id
                      LEFT JOIN execution.semantic_symbol AS target_factor_predicate
                        ON target_factor_predicate.symbol_id=target_factor.predicate_symbol_id
                      LEFT JOIN execution.semantic_pnf_demand AS target_demand
                        ON resolution.selected_target_kind=3
                       AND target_demand.demand_id=resolution.selected_target_id
                      LEFT JOIN execution.semantic_pnf_region AS target_demand_region
                        ON target_demand_region.region_id=target_demand.source_region_id
                      LEFT JOIN execution.semantic_symbol AS target_demand_residual
                        ON target_demand_residual.symbol_id=target_demand.residual_type_symbol_id
                      LEFT JOIN execution.semantic_pnf_object_token_support AS target_demand_support
                        ON target_demand_support.object_id=target_demand.source_object_id
                       AND target_demand_support.ordinal=0
                      LEFT JOIN execution.semantic_parser_token AS target_demand_token
                        ON target_demand_token.token_id=target_demand_support.token_id
                      LEFT JOIN execution.semantic_pnf_interface AS witness
                        ON witness.interface_id=resolution.witness_interface_id
                      LEFT JOIN execution.semantic_pnf_region AS witness_region
                        ON witness_region.region_id=witness.region_id
                     ORDER BY d.source_region_start,d.source_token_start,
                              interface_region.start_char
                    """,
                    scope,
                )

                affected_interfaces = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    SELECT DISTINCT interface_region.region_kind,
                                    interface_region.start_char,
                                    interface_region.end_char
                      FROM scoped_demand AS d
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=d.source_interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                     ORDER BY interface_region.start_char,interface_region.end_char
                    """,
                    scope,
                )

                affected_interface_authority = _rows(
                    cursor,
                    _DEMAND_CTE + """
                    , affected AS MATERIALIZED (
                        SELECT DISTINCT d.source_interface_id
                          FROM scoped_demand AS d
                         WHERE d.source_interface_id IS NOT NULL
                    )
                    SELECT interface_region.region_kind,
                           interface_region.start_char,
                           interface_region.end_char,
                           interface.interface_cardinality,
                           interface.promoted_object_count,
                           interface.unresolved_count,
                           count(export.target_id)::BIGINT,
                           count(export.target_id) FILTER (
                               WHERE export.target_kind=1
                           )::BIGINT,
                           count(export.target_id) FILTER (
                               WHERE export.target_kind=3
                           )::BIGINT
                      FROM affected
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.interface_id=affected.source_interface_id
                      JOIN execution.semantic_pnf_region AS interface_region
                        ON interface_region.region_id=interface.region_id
                      LEFT JOIN execution.semantic_pnf_interface_export AS export
                        ON export.interface_id=interface.interface_id
                     GROUP BY interface_region.region_kind,
                              interface_region.start_char,
                              interface_region.end_char,
                              interface.interface_cardinality,
                              interface.promoted_object_count,
                              interface.unresolved_count
                     ORDER BY interface_region.start_char,interface_region.end_char
                    """,
                    scope,
                )

                document_authority = _rows(
                    cursor,
                    """
                    SELECT source_region.region_kind,
                           source_region.start_char,
                           source_region.end_char,
                           source_region.closure_state,
                           interface.closure_state,
                           interface.interface_cardinality,
                           interface.promoted_object_count,
                           interface.unresolved_count,
                           count(export.target_id)::BIGINT
                      FROM execution.semantic_pnf_region AS source_region
                      JOIN execution.semantic_pnf_interface AS interface
                        ON interface.region_id=source_region.region_id
                      LEFT JOIN execution.semantic_pnf_interface_export AS export
                        ON export.interface_id=interface.interface_id
                     WHERE """ + _SCOPE + """
                       AND source_region.region_kind=10
                     GROUP BY source_region.region_kind,
                              source_region.start_char,
                              source_region.end_char,
                              source_region.closure_state,
                              interface.closure_state,
                              interface.interface_cardinality,
                              interface.promoted_object_count,
                              interface.unresolved_count
                     ORDER BY source_region.start_char,source_region.end_char
                    """,
                    scope,
                )

                return {
                    "source_pronouns": source_pronouns,
                    "mentions": mentions,
                    "mention_token_support": mention_token_support,
                    "object_token_support": object_token_support,
                    "object_mention_support": object_mention_support,
                    "affected_interfaces": affected_interfaces,
                    "demands": demands,
                    "demand_exports": demand_exports,
                    "demand_lookups": demand_lookups,
                    "occurrence_provenance": occurrence_provenance,
                    "candidates": candidates,
                    "frontier_resolutions": frontier_resolutions,
                    "affected_interface_authority": affected_interface_authority,
                    "document_authority": document_authority,
                }
    finally:
        connection.close()


def _has_delta_projector(database_url: str) -> bool:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT to_regprocedure(
                    'execution.project_numeric_sentence_anaphor_delta(bigint[])'
                ) IS NOT NULL
                """
            )
            return bool(cursor.fetchone()[0])
    finally:
        connection.close()


def _database_name(connection: Any) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("cannot resolve current database")
        return str(row[0])


def _prepare_function_profile(database_url: str) -> str:
    connection = connect(database_url)
    try:
        connection.autocommit = True
        database = _database_name(connection)
        escaped = database.replace('"', '""')
        with connection.cursor() as cursor:
            cursor.execute(f'ALTER DATABASE "{escaped}" SET track_functions = \'pl\'')
            cursor.execute("SELECT pg_stat_reset()")
        return database
    finally:
        connection.close()


def _run_replay(command: str, *, database_url: str) -> tuple[int, int]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    started = monotonic_ns()
    completed = subprocess.run(shlex.split(command), env=environment, check=False)
    return int(completed.returncode), monotonic_ns() - started


def _function_stats(database_url: str) -> dict[str, dict[str, int | float]]:
    wanted = (
        "project_numeric_sentence_anaphors_setwise",
        "project_numeric_sentence_anaphor_delta",
        "normalize_numeric_pnf_anaphor_referent_kind",
        "normalize_numeric_pnf_anaphor_surface",
    )
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT funcname,calls,total_time,self_time
                  FROM pg_stat_user_functions
                 WHERE schemaname='execution'
                   AND funcname=ANY(%s)
                 ORDER BY funcname
                """,
                (list(wanted),),
            )
            return {
                str(name): {
                    "calls": int(calls),
                    "total_ms": float(total_ms),
                    "self_ms": float(self_ms),
                }
                for name, calls, total_ms, self_ms in cursor.fetchall()
            }
    finally:
        connection.close()


def _maybe_replay(database_url: str, command: str | None) -> dict[str, Any]:
    if command is None:
        return {
            "executed_by_harness": False,
            "command": None,
            "returncode": None,
            "wall_ns": None,
            "functions": _function_stats(database_url),
        }
    database = _prepare_function_profile(database_url)
    returncode, wall_ns = _run_replay(command, database_url=database_url)
    return {
        "executed_by_harness": True,
        "database": database,
        "command": command,
        "returncode": returncode,
        "wall_ns": wall_ns,
        "functions": _function_stats(database_url),
    }


def _geometry(
    *,
    legacy_profile: dict[str, Any],
    e0d_profile: dict[str, Any],
    legacy_snapshot: dict[str, tuple[tuple[Any, ...], ...]],
    e0d_snapshot: dict[str, tuple[tuple[Any, ...], ...]],
) -> dict[str, Any]:
    legacy_functions = legacy_profile["functions"]
    e0d_functions = e0d_profile["functions"]
    legacy_adaptor = legacy_functions.get(
        "project_numeric_sentence_anaphors_setwise", {}
    )
    e0d_adaptor = e0d_functions.get(
        "project_numeric_sentence_anaphors_setwise", {}
    )
    e0d_projector = e0d_functions.get(
        "project_numeric_sentence_anaphor_delta", {}
    )
    legacy_calls = int(legacy_adaptor.get("calls", 0))
    e0d_adaptor_calls = int(e0d_adaptor.get("calls", 0))
    projector_calls = int(e0d_projector.get("calls", 0))
    return {
        "legacy_compatibility_or_projector_calls": legacy_calls,
        "e0d_compatibility_adaptor_calls": e0d_adaptor_calls,
        "e0d_semantic_projector_calls": projector_calls,
        "e0d_semantic_entry_reduction_ratio": (
            legacy_calls / projector_calls if projector_calls else None
        ),
        "legacy_pronoun_occurrence_count": len(legacy_snapshot["source_pronouns"]),
        "e0d_pronoun_occurrence_count": len(e0d_snapshot["source_pronouns"]),
        "legacy_affected_key_count": len(legacy_snapshot["affected_interfaces"]),
        "e0d_affected_key_count": len(e0d_snapshot["affected_interfaces"]),
        "performance_win_claimed": False,
    }


def certify_e0d(
    *,
    legacy_database_url: str,
    e0d_database_url: str,
    legacy_run_ref: str,
    e0d_run_ref: str,
    document_ref: str | None = None,
    legacy_command: str | None = None,
    e0d_command: str | None = None,
) -> dict[str, Any]:
    if _has_delta_projector(legacy_database_url):
        raise RuntimeError(
            "legacy database already contains migration-180 delta projector; "
            "use a scratch fixture migrated through 179"
        )
    if not _has_delta_projector(e0d_database_url):
        raise RuntimeError("E0d database does not contain migration-180 delta projector")

    legacy_profile = _maybe_replay(legacy_database_url, legacy_command)
    if legacy_profile.get("returncode") not in (None, 0):
        raise RuntimeError(
            f"legacy replay failed with returncode={legacy_profile['returncode']}"
        )
    e0d_profile = _maybe_replay(e0d_database_url, e0d_command)
    if e0d_profile.get("returncode") not in (None, 0):
        raise RuntimeError(
            f"E0d replay failed with returncode={e0d_profile['returncode']}"
        )

    legacy_snapshot = _snapshot(
        legacy_database_url,
        run_ref=legacy_run_ref,
        document_ref=document_ref,
    )
    e0d_snapshot = _snapshot(
        e0d_database_url,
        run_ref=e0d_run_ref,
        document_ref=document_ref,
    )
    parity = certify_layers(legacy_snapshot, e0d_snapshot, layers=LAYERS)

    source_count = len(e0d_snapshot["source_pronouns"])
    demand_count = len(e0d_snapshot["demands"])
    affected_count = len(e0d_snapshot["affected_interfaces"])
    fixture_sufficient = source_count >= 2 and demand_count >= 2 and affected_count >= 1

    return {
        "contract": CONTRACT,
        "comparison": {
            "legacy_schema": "through migration 179",
            "projected_schema": "through migration 180",
            "legacy_run_ref": legacy_run_ref,
            "e0d_run_ref": e0d_run_ref,
            "document_ref": document_ref,
            "portable_semantic_coordinates_only": True,
            "database_local_surrogate_ids_compared": False,
            "pnf_digests_with_local_id_preimages_compared": False,
            "surrogate_rank_compared": False,
            "portable_ordering_compared": True,
        },
        "formal_runtime_shape": {
            "source_delta": "source_pronouns",
            "projection_atoms": [
                "mentions",
                "mention_token_support",
                "object_token_support",
                "object_mention_support",
            ],
            "affected_keys": "affected_interfaces",
            "local_reducer": "affected_interface_authority",
            "authority_observer": [
                "demands",
                "demand_exports",
                "demand_lookups",
                "occurrence_provenance",
                "candidates",
                "frontier_resolutions",
                "document_authority",
            ],
        },
        "fixture": {
            "sufficient_for_substantive_e0d_gate": fixture_sufficient,
            "minimum_pronoun_occurrences": 2,
            "pronoun_occurrence_count": source_count,
            "anaphor_demand_count": demand_count,
            "affected_key_count": affected_count,
        },
        "authority_parity": parity,
        "execution": {
            "legacy": legacy_profile,
            "e0d": e0d_profile,
            "geometry": _geometry(
                legacy_profile=legacy_profile,
                e0d_profile=e0d_profile,
                legacy_snapshot=legacy_snapshot,
                e0d_snapshot=e0d_snapshot,
            ),
            "performance_win_claimed": False,
        },
        "promotion_gate": {
            "semantic_parity": parity["commuting_square_equal"],
            "fixture_sufficient": fixture_sufficient,
            "performance_evidence_present": bool(
                legacy_profile["executed_by_harness"]
                and e0d_profile["executed_by_harness"]
            ),
            "performance_win_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-database-url", required=True)
    parser.add_argument("--e0d-database-url", required=True)
    parser.add_argument("--legacy-run-ref", required=True)
    parser.add_argument("--e0d-run-ref", required=True)
    parser.add_argument("--document-ref")
    parser.add_argument("--legacy-command")
    parser.add_argument("--e0d-command")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = certify_e0d(
        legacy_database_url=args.legacy_database_url,
        e0d_database_url=args.e0d_database_url,
        legacy_run_ref=args.legacy_run_ref,
        e0d_run_ref=args.e0d_run_ref,
        document_ref=args.document_ref,
        legacy_command=args.legacy_command,
        e0d_command=args.e0d_command,
    )
    rendered = json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if not receipt["fixture"]["sufficient_for_substantive_e0d_gate"]:
        return 3
    if not receipt["authority_parity"]["commuting_square_equal"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
