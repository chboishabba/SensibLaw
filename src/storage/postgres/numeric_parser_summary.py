"""Compact execution summary for the strict numeric streamed parser.

Sentence/token/entity cardinalities are already maintained on each parser
partition at fenced completion.  Production summary therefore aggregates that
small execution ledger instead of rescanning the document-sized observation
tables.  Boundary obligations remain a separate exact row count because one
logical obligation may be encountered by more than one execution attempt.
"""

from __future__ import annotations

from src.storage.postgres.spacy_parser_model import (
    ParserExecutionSummary,
    connect,
)


def numeric_execution_summary(
    database_url: str,
    *,
    run_ref: str,
    document_ref: str,
    source_ref: str,
    parser_contract_ref: str,
) -> ParserExecutionSummary:
    connection = connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT coverage.state,
                       COALESCE(sum(partition.sentence_count), 0),
                       COALESCE(sum(partition.token_count), 0),
                       count(partition.partition_ref),
                       COALESCE(sum(partition.entity_count), 0)
                  FROM execution.semantic_parser_document_coverage AS coverage
                  LEFT JOIN execution.semantic_parser_partition AS partition
                    ON partition.run_ref = coverage.run_ref
                   AND partition.document_ref = coverage.document_ref
                 WHERE coverage.run_ref = %s
                   AND coverage.document_ref = %s
                 GROUP BY coverage.state
                """,
                (run_ref, document_ref),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("parser execution summary is missing")
            cursor.execute(
                """
                SELECT count(*)
                  FROM execution.semantic_parser_boundary_obligation
                 WHERE run_ref = %s AND document_ref = %s
                """,
                (run_ref, document_ref),
            )
            obligation_row = cursor.fetchone()
            boundary_obligation_count = (
                int(obligation_row[0]) if obligation_row is not None else 0
            )
    finally:
        connection.close()

    return ParserExecutionSummary(
        run_ref=run_ref,
        document_ref=document_ref,
        source_ref=source_ref,
        parser_contract_ref=parser_contract_ref,
        coverage_state=str(row[0]),
        sentence_count=int(row[1]),
        token_count=int(row[2]),
        partition_count=int(row[3]),
        entity_count=int(row[4]),
        boundary_obligation_count=boundary_obligation_count,
    )


__all__ = ["numeric_execution_summary"]
