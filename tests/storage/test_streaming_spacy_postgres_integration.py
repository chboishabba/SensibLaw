from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from src.storage.postgres.spacy_parser_model import ParserStreamingPolicy
from src.storage.postgres.streaming_spacy_execution import (
    run_streaming_spacy_execution,
)


def _database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        pytest.skip("DATABASE_URL is required for the typed spaCy integration probe")
    return value


def _policy(
    *,
    target_chars: int = 1_024,
    context_chars: int = 64,
    batch_size: int = 1,
    cache_docbin: bool = False,
) -> ParserStreamingPolicy:
    return ParserStreamingPolicy(
        target_chars=target_chars,
        context_chars=context_chars,
        batch_size=batch_size,
        cache_docbin=cache_docbin,
    )


def test_streamed_parser_commits_numeric_rows_and_pnf_hyperfabric(
    tmp_path: Path,
) -> None:
    database_url = _database_url()
    psycopg = pytest.importorskip("psycopg")
    pytest.importorskip("spacy")
    run_ref = f"numeric-spacy-probe:{uuid4().hex}"
    document_ref = f"document:numeric-spacy:{uuid4().hex}"
    second_run_ref = f"numeric-spacy-probe:{uuid4().hex}"
    second_document_ref = f"document:numeric-spacy:{uuid4().hex}"
    text = (
        "The café must retain the record. The officer may inspect it.\n\n"
        "Unless an exception applies, the duty continues."
    )

    try:
        carrier = run_streaming_spacy_execution(
            database_url=database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            canonical_text=text,
            parser_contract_ref="parser:spacy:integration:v1",
            artifact_root=tmp_path / "first",
            worker_count=1,
            policy=_policy(),
        )

        assert carrier.sentence_count >= 2
        assert carrier.token_count > 0
        assert carrier["parser_receipt"]["pnf_document_interface_id"] > 0
        assert (
            carrier["parser_receipt"]["pnf_segmentation_evaluations"]
            <= carrier["parser_receipt"]["pnf_segmentation_bound"]
        )
        sentences = tuple(carrier["sents"])
        assert len(sentences) == carrier.sentence_count
        assert all(
            "head_text" not in token
            for row in sentences
            for token in row["tokens"]
        )
        assert all(
            int(token["index"]) == int(token["start"])
            for row in sentences
            for token in row["tokens"]
        )

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT state, completed_partitions, total_partitions,
                           open_boundary_obligations
                    FROM execution.semantic_parser_document_coverage
                    WHERE run_ref = %s AND document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                state, completed, total, open_obligations = cursor.fetchone()
                assert state == "complete"
                assert int(completed) == int(total)
                assert int(open_obligations) == 0
                initial_partition_count = int(total)

                cursor.execute(
                    """
                    SELECT count(*),
                           bool_and(representation_version = 2),
                           bool_and(sentence_id IS NOT NULL),
                           bool_and(token_id IS NOT NULL),
                           bool_and(head_token_id IS NOT NULL),
                           bool_and(orth_symbol_id IS NOT NULL),
                           bool_and(lemma_symbol_id IS NOT NULL),
                           bool_and(dependency_symbol_id IS NOT NULL),
                           bool_and(orth_ref IS NULL),
                           bool_and(lemma_ref IS NULL),
                           bool_and(dependency_ref IS NULL)
                    FROM execution.semantic_parser_token
                    WHERE run_ref = %s AND document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                numeric_token_state = cursor.fetchone()
                assert int(numeric_token_state[0]) == carrier.token_count
                assert all(bool(value) for value in numeric_token_state[1:])

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_pnf_region
                    WHERE run_ref = %s AND document_ref = %s
                      AND region_kind = 1
                    """,
                    (run_ref, document_ref),
                )
                assert int(cursor.fetchone()[0]) == carrier.sentence_count

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_pnf_work_item
                    WHERE run_ref = %s AND state_id <> 3
                    """,
                    (run_ref,),
                )
                assert int(cursor.fetchone()[0]) == 0

                document_interface_id = int(
                    carrier["parser_receipt"]["pnf_document_interface_id"]
                )
                cursor.execute(
                    """
                    SELECT region.region_kind, interface.closure_state,
                           interface.interface_cardinality
                    FROM execution.semantic_pnf_interface AS interface
                    JOIN execution.semantic_pnf_region AS region
                      ON region.region_id = interface.region_id
                    WHERE interface.interface_id = %s
                    """,
                    (document_interface_id,),
                )
                region_kind, closure_state, cardinality = cursor.fetchone()
                assert int(region_kind) == 10
                assert int(closure_state) == 3
                assert int(cardinality) >= 0

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_pnf_interface_ancestor AS ancestor
                    JOIN execution.semantic_pnf_interface AS interface
                      ON interface.interface_id = ancestor.interface_id
                    JOIN execution.semantic_pnf_region AS region
                      ON region.region_id = interface.region_id
                    WHERE region.run_ref = %s
                      AND region.document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                assert int(cursor.fetchone()[0]) > 0

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_parser_graph_work
                    WHERE run_ref = %s AND document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                assert int(cursor.fetchone()[0]) == 0

        second = run_streaming_spacy_execution(
            database_url=database_url,
            run_ref=second_run_ref,
            document_ref=second_document_ref,
            canonical_text="The record remains available.",
            parser_contract_ref="parser:spacy:integration:v1",
            artifact_root=tmp_path / "second",
            worker_count=1,
            policy=_policy(),
        )
        assert second.token_count > 0

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*), count(DISTINCT token.lemma_symbol_id)
                    FROM execution.semantic_parser_token AS token
                    JOIN execution.semantic_symbol AS lemma
                      ON lemma.symbol_id = token.lemma_symbol_id
                    WHERE token.document_ref = ANY(%s)
                      AND lemma.kind_id = 2
                      AND lemma.symbol_text = 'the'
                    """,
                    ([document_ref, second_document_ref],),
                )
                occurrence_count, distinct_symbol_count = cursor.fetchone()
                assert int(occurrence_count) >= 2
                assert int(distinct_symbol_count) == 1

        resumed = run_streaming_spacy_execution(
            database_url=database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            canonical_text=text,
            parser_contract_ref="parser:spacy:integration:v1",
            artifact_root=tmp_path / "first",
            worker_count=2,
            policy=_policy(
                target_chars=2_048,
                context_chars=16,
                batch_size=4,
                cache_docbin=True,
            ),
        )
        assert resumed.sentence_count == carrier.sentence_count
        assert resumed.token_count == carrier.token_count

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*), max(attempt_count)
                    FROM execution.semantic_parser_partition
                    WHERE run_ref = %s AND document_ref = %s
                    """,
                    (run_ref, document_ref),
                )
                partition_count, max_attempt_count = cursor.fetchone()
                assert int(partition_count) == initial_partition_count
                assert int(max_attempt_count) == 1

        with pytest.raises(RuntimeError, match="contract identity changed"):
            run_streaming_spacy_execution(
                database_url=database_url,
                run_ref=run_ref,
                document_ref=document_ref,
                canonical_text=text,
                parser_contract_ref="parser:spacy:integration:v2",
                artifact_root=tmp_path / "first",
                worker_count=1,
                policy=_policy(),
            )
    finally:
        with psycopg.connect(database_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM execution.semantic_run WHERE run_ref = ANY(%s)",
                    ([run_ref, second_run_ref],),
                )
