from __future__ import annotations

import os

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import compile_directory_postgres
from src.storage.postgres import PostgresCompilerStore
from src.storage.postgres.enrichment_planner import load_external_lookup_demands


pytestmark = pytest.mark.live


def _planner_diagnostic(cursor, corpus_ref: str):
    cursor.execute(
        """
        SELECT
            demand.demand_ref,
            factor.factor_type_ref,
            demand.budget_class_ref,
            ARRAY_AGG(DISTINCT facet.facet_ref)
                FILTER (WHERE facet.facet_ref IS NOT NULL),
            ARRAY_AGG(DISTINCT alternative.type_ref)
                FILTER (WHERE alternative.type_ref IS NOT NULL),
            ARRAY_AGG(DISTINCT alternative.value_ref)
                FILTER (WHERE alternative.value_ref IS NOT NULL),
            ARRAY_AGG(DISTINCT anchor.parser_pos_ref)
                FILTER (WHERE anchor.parser_pos_ref IS NOT NULL),
            ARRAY_AGG(DISTINCT span_node.value_ref)
                FILTER (WHERE span_node.value_ref IS NOT NULL)
        FROM resolution.demand AS demand
        JOIN algebra.factor AS factor
          ON factor.factor_ref = demand.factor_ref
        JOIN algebra.factor_revision AS source_revision
          ON source_revision.factor_ref = demand.factor_ref
        LEFT JOIN resolution.demand_facet AS facet
          ON facet.demand_ref = demand.demand_ref
        LEFT JOIN algebra.factor_revision_alternative AS revision_alternative
          ON revision_alternative.factor_revision_ref = source_revision.factor_revision_ref
        LEFT JOIN algebra.alternative AS alternative
          ON alternative.alternative_ref = revision_alternative.alternative_ref
        LEFT JOIN pnf.factor_anchor AS anchor
          ON anchor.factor_revision_ref = source_revision.factor_revision_ref
        LEFT JOIN corpus.span AS mention_span
          ON mention_span.document_ref = anchor.document_ref
         AND mention_span.start_token = anchor.start_token
         AND mention_span.end_token = anchor.end_token
         AND mention_span.span_type_ref = 'licensed_mention'
        LEFT JOIN language.annotation_node AS span_node
          ON span_node.span_ref = mention_span.span_ref
         AND span_node.annotation_type_ref = 'licensed_mention'
        WHERE EXISTS (
            SELECT 1
            FROM corpus.document_occurrence AS occurrence
            WHERE occurrence.corpus_ref = %s
              AND occurrence.document_ref = factor.document_ref
        )
        GROUP BY demand.demand_ref, factor.factor_type_ref, demand.budget_class_ref
        ORDER BY demand.demand_ref
        LIMIT 20
        """,
        (corpus_ref,),
    )
    return cursor.fetchall()


def test_compiled_corpus_plans_external_lookups_without_network(tmp_path) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")

    source = tmp_path / "source.txt"
    source.write_text(
        "George W. Bush visited Texas. He discussed a policy framework.",
        encoding="utf-8",
    )
    store = PostgresCompilerStore.connect(database_url)
    try:
        compilation = compile_directory_postgres(
            tmp_path,
            context=default_compiler_context(),
            store=store,
        )
        assert compilation.failure_refs == ()
        with store.transaction() as cursor:
            demands = load_external_lookup_demands(
                cursor,
                corpus_ref=compilation.corpus_ref,
                limit=100,
            )
            diagnostic = _planner_diagnostic(cursor, compilation.corpus_ref)

        assert demands, diagnostic
        surfaces = {row.surface for row in demands}
        assert surfaces.intersection(
            {"George W. Bush", "George", "Bush", "Texas"}
        ), diagnostic
        assert all(row.surface != "He" for row in demands)
        assert any(row.demand_kind == "entity_identity" for row in demands)
        assert all(
            "postgres-external-lookup-plan:v0_1" in row.provenance_refs
            for row in demands
        )
    finally:
        store.close()
