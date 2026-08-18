"""Project strict sentence demand provenance from its existing producer fibre.

Migration 135's generic demand trigger is intentionally defensive: given only a
new demand row it searches the materialized graph to recover a unique producer
factor, trigger token, evidence tokens and any typed target occurrence. That is
appropriate for generic producers, but strict numeric sentence admission has
already staged exactly those factors/supports/slots before inserting its demand
rows.

This execution strategy keeps the same fail-closed producer rules while moving
the strict sentence path from one procedural reconstruction per demand to one
set-wise projection over the bounded sentence fibre. Other producers retain the
generic trigger unchanged.

The projection also preserves set geometry internally: object-support uniqueness
is computed once for the finite set of producer/evidence tokens rather than by a
correlated subquery for every occurrence row.
"""

from __future__ import annotations

from functools import wraps
from typing import Any


_INSTALL_MARKER = "_producer_native_sentence_provenance_installed"


def _project_provenance(cursor: Any) -> None:
    """Emit trigger/evidence/target occurrences for all staged sentence demands."""

    cursor.execute(
        """
        WITH producer_match AS (
            SELECT demand.demand_id,
                   demand.source_region_id,
                   factor_stage.ordinal AS factor_ordinal,
                   factor.factor_id,
                   support.token_id AS trigger_token_id
              FROM tmp_numeric_sentence_demand AS demand_stage
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_digest = demand_stage.demand_digest
              JOIN tmp_numeric_sentence_factor AS factor_stage
                ON factor_stage.factor_type_symbol_id =
                   demand_stage.expected_factor_type_symbol_id
              JOIN execution.semantic_pnf_factor AS factor
                ON factor.factor_digest = factor_stage.factor_digest
               AND factor.region_id = demand.source_region_id
              JOIN tmp_numeric_sentence_factor_support AS support
                ON support.factor_ordinal = factor_stage.ordinal
              JOIN execution.semantic_parser_token AS token
                ON token.token_id = support.token_id
               AND token.representation_version = 2
             WHERE demand_stage.expected_factor_type_symbol_id IS NOT NULL
               AND demand_stage.lexical_symbol_id IS NOT NULL
               AND token.lemma_symbol_id = demand_stage.lexical_symbol_id
        ),
        producer AS (
            SELECT demand_id,
                   min(source_region_id) AS source_region_id,
                   min(factor_ordinal) AS factor_ordinal,
                   min(factor_id) AS factor_id,
                   min(trigger_token_id) AS trigger_token_id
              FROM producer_match
             GROUP BY demand_id
            HAVING count(*) = 1
        ),
        evidence_base AS (
            SELECT producer.demand_id,
                   producer.source_region_id,
                   producer.factor_id,
                   support.token_id,
                   support.ordinal AS support_ordinal
              FROM producer
              JOIN execution.semantic_pnf_factor_token_support AS support
                ON support.factor_id = producer.factor_id
             WHERE support.token_id <> producer.trigger_token_id
        ),
        occurrence_token AS (
            SELECT source_region_id, trigger_token_id AS token_id
              FROM producer
            UNION
            SELECT source_region_id, token_id
              FROM evidence_base
        ),
        unique_object AS (
            SELECT occurrence.source_region_id,
                   occurrence.token_id,
                   min(support.object_id) AS object_id
              FROM occurrence_token AS occurrence
              JOIN execution.semantic_pnf_object_token_support AS support
                ON support.token_id = occurrence.token_id
              JOIN execution.semantic_pnf_object AS object
                ON object.object_id = support.object_id
               AND object.region_id = occurrence.source_region_id
             GROUP BY occurrence.source_region_id, occurrence.token_id
            HAVING count(DISTINCT support.object_id) = 1
        ),
        trigger_rows AS (
            SELECT producer.demand_id,
                   1::SMALLINT AS occurrence_role,
                   producer.trigger_token_id AS token_id,
                   object_support.object_id,
                   0::SMALLINT AS ordinal,
                   'numeric-factor:' || producer.factor_id::TEXT AS producer_ref
              FROM producer
              LEFT JOIN unique_object AS object_support
                ON object_support.source_region_id = producer.source_region_id
               AND object_support.token_id = producer.trigger_token_id
        ),
        evidence_rows AS (
            SELECT evidence.demand_id,
                   3::SMALLINT AS occurrence_role,
                   evidence.token_id,
                   object_support.object_id,
                   (row_number() OVER (
                       PARTITION BY evidence.demand_id
                       ORDER BY evidence.support_ordinal, evidence.token_id
                   ) - 1)::SMALLINT AS ordinal,
                   'numeric-factor:' || evidence.factor_id::TEXT AS producer_ref
              FROM evidence_base AS evidence
              LEFT JOIN unique_object AS object_support
                ON object_support.source_region_id = evidence.source_region_id
               AND object_support.token_id = evidence.token_id
        ),
        target_match AS (
            SELECT producer.demand_id,
                   producer.factor_id,
                   support.token_id,
                   edge.object_id
              FROM producer
              JOIN execution.semantic_pnf_demand AS demand
                ON demand.demand_id = producer.demand_id
              JOIN execution.semantic_pnf_demand_target_role_rule AS rule
                ON rule.residual_type_symbol_id = demand.residual_type_symbol_id
              JOIN execution.semantic_pnf_hyperedge AS edge
                ON edge.factor_id = producer.factor_id
               AND edge.role_symbol_id = rule.target_role_symbol_id
              JOIN execution.semantic_pnf_object_token_support AS support
                ON support.object_id = edge.object_id
        ),
        target_rows AS (
            SELECT demand_id,
                   2::SMALLINT AS occurrence_role,
                   min(token_id) AS token_id,
                   min(object_id) AS object_id,
                   0::SMALLINT AS ordinal,
                   'numeric-factor:' || min(factor_id)::TEXT AS producer_ref
              FROM target_match
             GROUP BY demand_id
            HAVING count(*) = 1
        ),
        occurrence AS (
            SELECT * FROM trigger_rows
            UNION ALL
            SELECT * FROM target_rows
            UNION ALL
            SELECT * FROM evidence_rows
        )
        INSERT INTO execution.semantic_pnf_demand_occurrence_provenance
            (demand_id, occurrence_role, token_id, object_id, ordinal, producer_ref)
        SELECT demand_id,
               occurrence_role,
               token_id,
               object_id,
               ordinal,
               producer_ref
          FROM occurrence
        ON CONFLICT (demand_id, occurrence_role, token_id, ordinal) DO UPDATE SET
            object_id = EXCLUDED.object_id,
            producer_ref = EXCLUDED.producer_ref
        """
    )


def install_producer_native_sentence_provenance() -> bool:
    """Wrap strict sentence admission without replacing its semantic producer."""

    from src.storage.postgres import numeric_sentence_admission as admission

    if getattr(admission, _INSTALL_MARKER, False):
        return False

    original = admission.persist_sentence_closure_setwise

    @wraps(original)
    def persist_with_provenance(cursor: Any, *args: Any, **kwargs: Any) -> int:
        # Migration 147 makes this transaction-local flag suppress only the
        # generic occurrence reconstruction trigger. Every non-strict producer
        # continues to use that defensive database path.
        cursor.execute(
            "SELECT set_config("
            "'sensiblaw.direct_sentence_demand_provenance', 'on', TRUE)"
        )
        interface_id = int(original(cursor, *args, **kwargs))
        _project_provenance(cursor)
        return interface_id

    admission.persist_sentence_closure_setwise = persist_with_provenance
    setattr(admission, _INSTALL_MARKER, True)
    return True


__all__ = ["install_producer_native_sentence_provenance"]
