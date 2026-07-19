from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from src.policy.corpus_compilation import default_compiler_context
from src.policy.postgres_corpus_compilation import compile_directory_postgres
from src.storage.postgres import PostgresCompilerStore


pytestmark = pytest.mark.live


def test_gwb_mini_compiles_into_postgres_without_json_outputs() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "corpora"
        / "gwb-mini"
    )
    if not fixture.exists():
        pytest.skip("gwb-mini fixture is not present on this branch")
    store = PostgresCompilerStore.connect(database_url)
    try:
        first = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        second = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        assert first.corpus_ref == second.corpus_ref
        assert first.document_refs == second.document_refs
        assert first.demand_refs == second.demand_refs
        assert first.failure_refs == ()
        assert store.unresolved_demands(first.corpus_ref)
        for document_ref in first.document_refs:
            summary = store.document_summary(document_ref)
            assert summary is not None
            assert summary["factor_count"] > 0
    finally:
        store.close()


def test_html_source_and_canonical_coordinates_remain_distinct(tmp_path: Path) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL integration proof")

    html = """
    <html data-pnf-poison="raw-tag">
      <head><style>.hidden { display: none; }</style></head>
      <body>
        <h1>George W. Bush</h1>
        <p>President Bush signed the Patriot Act. He discussed the law.</p>
        <script>RawTagActor should never be parsed.</script>
      </body>
    </html>
    """
    fixture = tmp_path / "html-canonical-corpus"
    fixture.mkdir()
    (fixture / "bush.html").write_text(html, encoding="utf-8")

    store = PostgresCompilerStore.connect(database_url)
    try:
        first = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        assert first.failure_refs == ()
        assert len(first.document_refs) == 1
        document_ref = first.document_refs[0]

        with store.transaction() as cursor:
            cursor.execute(
                """
                SELECT source.payload, canonical.payload,
                       encode(canonical.content_sha256, 'hex')
                FROM corpus.document AS document
                JOIN corpus.binary_content AS source
                  ON source.content_ref = document.source_content_ref
                JOIN corpus.canonical_content AS canonical
                  ON canonical.canonical_ref = document.canonical_ref
                WHERE document.document_ref = %s
                """,
                (document_ref,),
            )
            source_payload, canonical_payload, canonical_sha256 = cursor.fetchone()
            source_text = bytes(source_payload).decode("utf-8")
            canonical_text = bytes(canonical_payload).decode("utf-8")

            cursor.execute(
                """
                SELECT span.start_char, span.end_char, node.value_ref
                FROM corpus.span AS span
                JOIN language.annotation_node AS node
                  ON node.span_ref = span.span_ref
                WHERE span.document_ref = %s
                  AND span.span_type_ref = 'licensed_mention'
                  AND node.annotation_type_ref = 'licensed_mention'
                ORDER BY span.start_char, span.end_char, span.span_ref
                """,
                (document_ref,),
            )
            mention_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT DISTINCT lexeme.normalized_text
                FROM language.tokenizer_run AS run
                JOIN language.token_stream_chunk AS chunk
                  ON chunk.tokenizer_run_ref = run.tokenizer_run_ref
                JOIN language.codec_symbol AS symbol
                  ON symbol.codec_ref = chunk.codec_ref
                JOIN language.lexeme AS lexeme
                  ON lexeme.lexeme_id = symbol.lexeme_id
                WHERE run.document_ref = %s
                ORDER BY lexeme.normalized_text
                """,
                (document_ref,),
            )
            persisted_lexemes = {str(row[0]) for row in cursor.fetchall()}

        assert "data-pnf-poison" in source_text
        assert "RawTagActor" in source_text
        assert "George W. Bush" in canonical_text
        assert "Patriot Act" in canonical_text
        assert "data-pnf-poison" not in canonical_text
        assert "RawTagActor" not in canonical_text
        assert "<html" not in canonical_text
        assert canonical_sha256 == hashlib.sha256(
            canonical_text.encode("utf-8")
        ).hexdigest()
        assert mention_rows
        for start_char, end_char, surface in mention_rows:
            assert canonical_text[int(start_char) : int(end_char)] == str(surface)
        assert "george" in persisted_lexemes
        assert "bush" in persisted_lexemes
        assert "rawtagactor" not in persisted_lexemes
        assert "data" not in persisted_lexemes
        assert "pnf" not in persisted_lexemes
        assert "poison" not in persisted_lexemes
        assert not any("<" in token or ">" in token for token in persisted_lexemes)

        second = compile_directory_postgres(
            fixture,
            context=default_compiler_context(),
            store=store,
        )
        assert second.corpus_ref == first.corpus_ref
        assert second.document_refs == first.document_refs
        assert second.demand_refs == first.demand_refs
        assert second.failure_refs == ()
        with store.transaction() as cursor:
            cursor.execute(
                """
                SELECT occurrence_state
                FROM corpus.document_occurrence
                WHERE corpus_ref = %s
                """,
                (first.corpus_ref,),
            )
            assert {str(row[0]) for row in cursor.fetchall()} == {
                "reused_compilation"
            }
    finally:
        store.close()
