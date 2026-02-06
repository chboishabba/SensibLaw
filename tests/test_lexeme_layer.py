from __future__ import annotations

from datetime import date

from src.models.document import Document, DocumentMetadata
from src.storage.versioned_store import VersionedStore


def test_lexeme_occurrences_are_span_anchored(tmp_path):
    store = VersionedStore(tmp_path / "lexeme.db")
    try:
        metadata = DocumentMetadata(
            jurisdiction="AU.TEST",
            citation="LEX-001",
            date=date(2024, 1, 1),
        )
        body = "Token token TOKEN."
        doc = Document(metadata=metadata, body=body)
        doc_id = store.generate_id()
        store.add_revision(doc_id, doc, date(2024, 1, 1))

        lexemes = store.conn.execute(
            "SELECT norm_text, norm_kind FROM lexemes ORDER BY norm_text"
        ).fetchall()
        assert [(row["norm_text"], row["norm_kind"]) for row in lexemes] == [
            (".", "punct"),
            ("token", "word"),
        ]

        occs = store.conn.execute(
            """
            SELECT occ_id, start_char, end_char, token_index
            FROM lexeme_occurrences
            WHERE doc_id = ?
            ORDER BY occ_id
            """,
            (doc_id,),
        ).fetchall()
        assert [(row["start_char"], row["end_char"]) for row in occs] == [
            (0, 5),
            (6, 11),
            (12, 17),
            (17, 18),
        ]
        assert [row["token_index"] for row in occs] == [0, 1, 2, 3]
    finally:
        store.close()
