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


def test_streamed_parser_commits_typed_rows_and_graph_readiness(
    tmp_path: Path,
) -> None:
    database_url = _database_url()
    psycopg = pytest.importorskip("psycopg")
    pytest.importorskip("spacy")
    run_ref = f"typed-spacy-probe:{uuid4().hex}"
    document_ref = f"document:typed-spacy:{uuid4().hex}"
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
            artifact_root=tmp_path,
            worker_count=1,
            policy=ParserStreamingPolicy(
                target_chars=1_024,
                context_chars=64,
                batch_size=1,
                cache_docbin=False,
            ),
        )

        assert carrier.sentence_count >= 2
        assert carrier.token_count > 0
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
                    SELECT count(*)
                    FROM execution.semantic_parser_graph_work
                    WHERE run_ref = %s AND document_ref = %s
                      AND scope_kind = 'sentence'
                    """,
                    (run_ref, document_ref),
                )
                assert int(cursor.fetchone()[0]) == carrier.sentence_count * 3

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_parser_graph_work
                    WHERE run_ref = %s AND document_ref = %s
                      AND scope_kind = 'document'
                      AND operation_kind = 'document_closure'
                      AND parser_coverage_required
                    """,
                    (run_ref, document_ref),
                )
                assert int(cursor.fetchone()[0]) == 1

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM execution.semantic_work_item AS work
                    JOIN execution.semantic_parser_graph_work AS parser_work
                      USING (work_ref)
                    WHERE parser_work.run_ref = %s
                      AND work.state = 'ready'
                    """,
                    (run_ref,),
                )
                assert int(cursor.fetchone()[0]) == carrier.sentence_count * 3 + 1

        # Physical retuning is semantically inert.  The second invocation must
        # reuse the registered partition plan and completed observations rather
        # than insert a differently partitioned plan or load spaCy again.
        resumed = run_streaming_spacy_execution(
            database_url=database_url,
            run_ref=run_ref,
            document_ref=document_ref,
            canonical_text=text,
            parser_contract_ref="parser:spacy:integration:v1",
            artifact_root=tmp_path,
            worker_count=2,
            policy=ParserStreamingPolicy(
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
                artifact_root=tmp_path,
                worker_count=1,
                policy=ParserStreamingPolicy(
                    target_chars=1_024,
                    context_chars=64,
                    cache_docbin=False,
                ),
            )
    finally:
        with psycopg.connect(database_url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM execution.semantic_run WHERE run_ref = %s",
                    (run_ref,),
                )
