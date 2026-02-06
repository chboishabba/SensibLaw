from __future__ import annotations

from src.text.compression_stats import compute_compression_stats
from src.text.lexeme_normalizer import normalize_lexeme
from src.models.document import Document, DocumentMetadata
from src.storage.versioned_store import VersionedStore
from datetime import date


def test_compression_stats_includes_lexeme_metrics():
    stats = compute_compression_stats("Token token TOKEN.")
    payload = stats.to_dict()
    assert payload["token_count"] > 0
    assert payload["unique_lexemes"] == 1  # punctuation excluded by tokenizer
    assert payload["tokenizer_id"] == "lexeme_normalizer_v1"


def test_rr5_and_mvd_shift_with_case_noise():
    surface = (
        ["Token", "must", "be", "a", "Token"] * 20
        + ["TOKEN", "must", "be", "a", "token"] * 20
        + ["ToKeN", "must", "be", "a", "TOKEN"] * 20
    )
    lexemes = [normalize_lexeme(t).norm_text for t in surface]

    stats_surface = compute_compression_stats(" ".join(surface)).to_dict()
    stats_lexeme = compute_compression_stats(" ".join(lexemes)).to_dict()

    assert stats_lexeme["rr5_lexeme"] >= stats_surface["rr5_lexeme"]
    assert stats_surface["mvd_lexeme"] >= stats_lexeme["mvd_lexeme"]


def test_compression_stats_persisted_matches_db(tmp_path):
    store = VersionedStore(tmp_path / "compress.db")
    try:
        metadata = DocumentMetadata(
            jurisdiction="AU.TEST",
            citation="COMP-001",
            date=date(2024, 1, 1),
        )
        body = "Token token TOKEN."
        metadata.compression_stats = compute_compression_stats(body).to_dict()
        doc = Document(metadata=metadata, body=body)

        doc_id = store.generate_id()
        store.add_revision(doc_id, doc, date(2024, 1, 1))

        row = store.conn.execute(
            "SELECT metadata, body FROM revisions WHERE doc_id = ? AND rev_id = 1",
            (doc_id,),
        ).fetchone()
        assert row is not None
        stored = DocumentMetadata.from_dict(__import__("json").loads(row["metadata"]))
        recomputed = compute_compression_stats(row["body"]).to_dict()
        assert stored.compression_stats == recomputed
    finally:
        store.close()
