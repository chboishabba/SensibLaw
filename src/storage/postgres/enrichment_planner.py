"""Project external lookup work directly from normalized PostgreSQL PNF rows."""

from __future__ import annotations

from typing import Any

from src.ontology.external_enrichment import ExternalLookupDemand


POSTGRES_EXTERNAL_PLAN_REF = "postgres-external-lookup-plan:v0_1"
_ENTITY_POS = frozenset({"PROPN"})
_LEXICAL_POS = frozenset({"ADJ", "ADV", "NOUN", "VERB"})


def _is_pronominal(type_refs: tuple[str, ...], parser_pos: str | None) -> bool:
    if parser_pos == "PRON":
        return True
    return any(
        "pronoun" in value.casefold() or "pronominal" in value.casefold()
        for value in type_refs
    )


def _entity_shaped(type_refs: tuple[str, ...], parser_pos: str | None) -> bool:
    if parser_pos in _ENTITY_POS:
        return True
    return any(
        marker in value.casefold()
        for value in type_refs
        for marker in ("named_entity", "proper_noun", "semantic-family:entity")
    )


def load_external_lookup_demands(
    cursor: Any,
    *,
    corpus_ref: str | None = None,
    limit: int = 1_000,
    include_wiktionary: bool = True,
) -> tuple[ExternalLookupDemand, ...]:
    """Load candidate-only provider work from persisted open demands.

    The demand names the active factor revision. Mention surfaces and parser
    anchors are recovered over the immutable revision family of the same stable
    factor because local refinements need not duplicate those structural rows.
    Residual state remains anchored to the demand's active revision.
    """

    if limit < 1:
        raise ValueError("external lookup plan limit must be positive")
    cursor.execute(
        """
        SELECT
            demand.demand_ref,
            demand.factor_ref,
            demand.factor_revision_ref,
            factor.factor_type_ref,
            MIN(anchor.parser_pos_ref) AS parser_pos_ref,
            MIN(node.value_ref) AS surface,
            COALESCE(
                ARRAY_AGG(DISTINCT alternative.type_ref)
                    FILTER (WHERE alternative.type_ref IS NOT NULL),
                ARRAY[]::TEXT[]
            ) AS local_type_refs,
            COALESCE(
                ARRAY_AGG(DISTINCT residual.residual_type_ref)
                    FILTER (WHERE residual.residual_type_ref IS NOT NULL),
                ARRAY[]::TEXT[]
            ) AS residual_refs
        FROM resolution.demand AS demand
        JOIN algebra.factor AS factor
          ON factor.factor_ref = demand.factor_ref
        JOIN algebra.factor_revision AS active_revision
          ON active_revision.factor_revision_ref = demand.factor_revision_ref
         AND active_revision.factor_ref = demand.factor_ref
        JOIN algebra.factor_revision AS source_revision
          ON source_revision.factor_ref = demand.factor_ref
        LEFT JOIN pnf.factor_anchor AS anchor
          ON anchor.factor_revision_ref = source_revision.factor_revision_ref
        LEFT JOIN algebra.factor_revision_alternative AS revision_alternative
          ON revision_alternative.factor_revision_ref = source_revision.factor_revision_ref
        LEFT JOIN algebra.alternative AS alternative
          ON alternative.alternative_ref = revision_alternative.alternative_ref
        LEFT JOIN language.annotation_node AS node
          ON node.annotation_node_ref = alternative.value_ref
         AND node.annotation_type_ref = 'licensed_mention'
        LEFT JOIN algebra.residual AS residual
          ON residual.target_ref = demand.factor_revision_ref
         AND residual.residual_state_ref = 'open'
        WHERE demand.demand_state_ref = 'open'
          AND demand.budget_class_ref = 'bounded_external_evidence'
          AND (CAST(%s AS TEXT) IS NULL OR EXISTS (
              SELECT 1
              FROM corpus.document_occurrence AS occurrence
              WHERE occurrence.corpus_ref = %s
                AND occurrence.document_ref = factor.document_ref
          ))
        GROUP BY
            demand.demand_ref,
            demand.factor_ref,
            demand.factor_revision_ref,
            factor.factor_type_ref
        HAVING MIN(node.value_ref) IS NOT NULL
        ORDER BY
            CASE WHEN MIN(anchor.parser_pos_ref) = 'PROPN' THEN 0 ELSE 1 END,
            demand.demand_ref
        LIMIT %s
        """,
        (corpus_ref, corpus_ref, limit),
    )
    projected: list[ExternalLookupDemand] = []
    for row in cursor.fetchall():
        (
            demand_ref,
            factor_ref,
            factor_revision_ref,
            factor_type,
            parser_pos,
            surface,
            local_type_refs,
            residual_refs,
        ) = row
        normalized_surface = str(surface or "").strip()
        if not normalized_surface:
            continue
        type_refs = tuple(sorted(str(value) for value in local_type_refs or ()))
        residuals = {str(value) for value in residual_refs or ()}
        pos = str(parser_pos) if parser_pos is not None else None
        if _is_pronominal(type_refs, pos):
            continue
        provenance = (
            str(factor_revision_ref),
            POSTGRES_EXTERNAL_PLAN_REF,
        )
        if (
            str(factor_type) == "semantic.mention_identity"
            and "external_identity_unresolved" in residuals
            and _entity_shaped(type_refs, pos)
        ):
            projected.append(
                ExternalLookupDemand(
                    demand_ref=str(demand_ref),
                    subject_ref=str(factor_ref),
                    surface=normalized_surface,
                    demand_kind="entity_identity",
                    local_type_refs=type_refs,
                    priority=100,
                    provenance_refs=provenance,
                )
            )
            continue
        if (
            include_wiktionary
            and pos in _LEXICAL_POS
            and residuals.intersection(
                {"local_type_unresolved", "external_identity_unresolved"}
            )
        ):
            projected.append(
                ExternalLookupDemand(
                    demand_ref=str(demand_ref),
                    subject_ref=str(factor_ref),
                    surface=normalized_surface,
                    demand_kind="lexical_sense",
                    local_type_refs=type_refs,
                    priority=10,
                    provenance_refs=provenance,
                )
            )
    return tuple(
        sorted(
            {
                (row.demand_ref, row.demand_kind, row.lookup_key): row
                for row in projected
            }.values(),
            key=lambda row: (-row.priority, row.demand_ref, row.demand_kind),
        )
    )


__all__ = ["POSTGRES_EXTERNAL_PLAN_REF", "load_external_lookup_demands"]
