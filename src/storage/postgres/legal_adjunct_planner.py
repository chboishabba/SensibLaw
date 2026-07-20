"""Project legal adjunct work from normalized PostgreSQL PNF demands."""

from __future__ import annotations

from typing import Any

from src.pnf.legal_adjunct import (
    LegalSourcePlan,
    NormativeInteractionDemand,
    plan_legal_sources,
    project_normative_interaction_demands,
)

POSTGRES_LEGAL_ADJUNCT_PLAN_REF = "postgres-legal-adjunct-plan:v0_1"


def load_normative_interaction_demands(
    cursor: Any,
    *,
    corpus_ref: str | None = None,
    limit: int = 500,
) -> tuple[NormativeInteractionDemand, ...]:
    """Load explicit legal work from open normalized resolution demands.

    The SQL reads only demand facets and immutable PNF identities. It does not
    route from predicate lemmas, surfaces, source filenames, or document family.
    A structural signature must be supplied as a normalized legal facet.
    """

    if limit < 1:
        raise ValueError("legal adjunct plan limit must be positive")
    cursor.execute(
        """
        SELECT
            demand.demand_ref,
            demand.factor_ref,
            demand.factor_revision_ref,
            COALESCE(
                ARRAY_AGG(DISTINCT facet.facet_ref)
                    FILTER (WHERE facet.facet_ref IS NOT NULL),
                ARRAY[]::TEXT[]
            ) AS requested_facets
        FROM resolution.demand AS demand
        JOIN algebra.factor AS factor
          ON factor.factor_ref = demand.factor_ref
        LEFT JOIN resolution.demand_facet AS facet
          ON facet.demand_ref = demand.demand_ref
        WHERE demand.demand_state_ref = 'open'
          AND demand.budget_class_ref = 'bounded_external_evidence'
          AND EXISTS (
              SELECT 1
              FROM resolution.demand_facet AS legal_facet
              WHERE legal_facet.demand_ref = demand.demand_ref
                AND left(legal_facet.facet_ref, length('legal.')) = 'legal.'
          )
          AND (CAST(%s AS TEXT) IS NULL OR EXISTS (
              SELECT 1
              FROM corpus.document_occurrence AS occurrence
              WHERE occurrence.corpus_ref = %s
                AND occurrence.document_ref = factor.document_ref
          ))
        GROUP BY
            demand.demand_ref,
            demand.factor_ref,
            demand.factor_revision_ref
        ORDER BY demand.demand_ref
        LIMIT %s
        """,
        (corpus_ref, corpus_ref, limit),
    )
    rows = []
    for demand_ref, factor_ref, factor_revision_ref, facets in cursor.fetchall():
        normalized_facets = tuple(sorted(str(value) for value in facets or ()))
        signature_values = tuple(
            value[len("legal.interaction_signature:") :]
            for value in normalized_facets
            if value.startswith("legal.interaction_signature:")
        )
        rows.append(
            {
                "demand_ref": str(demand_ref),
                "factor_ref": str(factor_ref),
                "factor_revision_ref": str(factor_revision_ref),
                "structural_signature_ref": signature_values[0] if signature_values else "",
                "requested_facets": normalized_facets,
                "provenance_refs": (
                    str(factor_revision_ref),
                    POSTGRES_LEGAL_ADJUNCT_PLAN_REF,
                ),
            }
        )
    return project_normative_interaction_demands(rows)


def load_legal_source_plans(
    cursor: Any,
    *,
    corpus_ref: str | None = None,
    limit: int = 500,
) -> tuple[LegalSourcePlan, ...]:
    return plan_legal_sources(
        load_normative_interaction_demands(
            cursor,
            corpus_ref=corpus_ref,
            limit=limit,
        )
    )


def load_legal_pnf_rows(
    cursor: Any,
    *,
    corpus_ref: str,
) -> tuple[dict[str, Any], ...]:
    """Load only PNF factors already typed as legal for Legal IR projection."""

    cursor.execute(
        """
        SELECT
            factor.factor_ref,
            revision.factor_revision_ref,
            factor.factor_type_ref,
            COALESCE(
                ARRAY_AGG(DISTINCT alternative.type_ref)
                    FILTER (WHERE alternative.type_ref IS NOT NULL),
                ARRAY[]::TEXT[]
            ) AS alternative_types
        FROM algebra.factor AS factor
        JOIN algebra.factor_revision AS revision
          ON revision.factor_ref = factor.factor_ref
        LEFT JOIN algebra.factor_revision_alternative AS link
          ON link.factor_revision_ref = revision.factor_revision_ref
        LEFT JOIN algebra.alternative AS alternative
          ON alternative.alternative_ref = link.alternative_ref
        WHERE EXISTS (
            SELECT 1
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
              AND occurrence.document_ref = factor.document_ref
        )
          AND (
              left(factor.factor_type_ref, length('semantic.legal.')) = 'semantic.legal.'
              OR factor.factor_type_ref IN (
                  'semantic.normative_relation',
                  'semantic.legal_condition',
                  'semantic.legal_exception',
                  'semantic.legal_burden',
                  'semantic.legal_authority',
                  'semantic.legal_transition',
                  'semantic.judicial_treatment'
              )
          )
        GROUP BY factor.factor_ref, revision.factor_revision_ref, factor.factor_type_ref
        ORDER BY factor.factor_ref, revision.factor_revision_ref
        """,
        (corpus_ref,),
    )
    return tuple(
        {
            "factor_ref": str(factor_ref),
            "factor_revision_ref": str(revision_ref),
            "factor_type_ref": str(factor_type),
            "structural_signature_ref": "pnf-signature:" + str(factor_type),
            "predicate_ref": str(factor_type),
            "role_bindings": {},
            "qualifier_state": {"alternative_type_refs": list(alternative_types or ())},
            "wrapper_state": {"source_corpus_ref": corpus_ref},
            "provenance_refs": (str(revision_ref), corpus_ref),
            "residual_refs": ("legal_role_binding_unresolved",),
        }
        for factor_ref, revision_ref, factor_type, alternative_types in cursor.fetchall()
    )


__all__ = [
    "POSTGRES_LEGAL_ADJUNCT_PLAN_REF",
    "load_legal_pnf_rows",
    "load_legal_source_plans",
    "load_normative_interaction_demands",
]
