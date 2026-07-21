from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from scripts.run_gwb_binding_baseline import _coordinate_report
from src.policy.corpus_compilation import (
    build_corpus_manifest,
    default_compiler_context,
)
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
    source_path = fixture / "bush.html"
    source_path.write_text(html, encoding="utf-8")
    source_bytes = html.encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    context = default_compiler_context()
    raw_manifest = build_corpus_manifest(fixture, context=context).to_dict()
    source_document_ref = str(raw_manifest["ordered_documents"][0]["document_ref"])

    store = PostgresCompilerStore.connect(database_url)
    try:
        # Seed the pre-v0.8 collision shape: raw HTML was both source and
        # canonical payload under the source-only document identity.
        with store.transaction() as cursor:
            store.persist_context(cursor, context.to_dict())
            store.persist_source_document(
                cursor,
                document_ref=source_document_ref,
                media_type="text/html",
                content_sha256=source_sha256,
                source_bytes=source_bytes,
                canonical_text=html,
                adapter_ref="media:html:v0_1",
                adapter_version=context.media_normalization_ref,
                compiler_context_ref=context.context_ref,
                normalization_ref=context.media_normalization_ref,
            )

        first = compile_directory_postgres(
            fixture,
            context=context,
            store=store,
        )
        assert first.failure_refs == ()
        assert len(first.document_refs) == 1
        document_ref = first.document_refs[0]
        assert document_ref != source_document_ref

        coordinate_report = _coordinate_report(store, first.corpus_ref)
        assert coordinate_report["documents"] == 1
        assert coordinate_report["html_documents"] == 1
        assert coordinate_report["source_equals_canonical_documents"] == 0
        assert coordinate_report["canonical_markup_documents"] == 0
        assert coordinate_report["licensed_mentions"] > 0
        assert coordinate_report["licensed_mention_surface_mismatches"] == 0
        assert coordinate_report["markup_fragment_mentions"] == 0
        assert coordinate_report["markup_lexemes"] == 0

        with store.transaction() as cursor:
            cursor.execute(
                """
                SELECT document.document_ref, source.payload, canonical.payload,
                       encode(canonical.content_sha256, 'hex')
                FROM corpus.document AS document
                JOIN corpus.binary_content AS source
                  ON source.content_ref = document.source_content_ref
                JOIN corpus.canonical_content AS canonical
                  ON canonical.canonical_ref = document.canonical_ref
                WHERE document.document_ref = ANY(%s)
                ORDER BY document.document_ref
                """,
                ([source_document_ref, document_ref],),
            )
            document_rows = {
                str(row[0]): (bytes(row[1]), bytes(row[2]), str(row[3]))
                for row in cursor.fetchall()
            }
            source_payload, canonical_payload, canonical_sha256 = document_rows[
                document_ref
            ]
            old_source_payload, old_canonical_payload, _old_sha256 = document_rows[
                source_document_ref
            ]
            source_text = source_payload.decode("utf-8")
            canonical_text = canonical_payload.decode("utf-8")

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

        assert old_source_payload == source_bytes
        assert old_canonical_payload == source_bytes
        assert source_text == html
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
            context=context,
            store=store,
        )
        assert second.corpus_ref == first.corpus_ref
        assert second.document_refs == first.document_refs
        assert second.demand_refs == first.demand_refs
        assert second.failure_refs == ()
        assert _coordinate_report(store, second.corpus_ref) == coordinate_report
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
