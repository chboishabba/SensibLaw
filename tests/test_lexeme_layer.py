from __future__ import annotations

import hashlib
import json

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


def test_add_revision_stores_tokenizer_profile(tmp_path):
    store = VersionedStore(tmp_path / "lexeme_profile.db")
    try:
        metadata = DocumentMetadata(
            jurisdiction="AU.TEST",
            citation="LEX-002",
            date=date(2024, 1, 2),
        )
        body = "Token token TOKEN."
        doc = Document(metadata=metadata, body=body)
        doc_id = store.generate_id()
        store.add_revision(doc_id, doc, date(2024, 1, 2))

        row = store.conn.execute(
            "SELECT metadata FROM revisions WHERE doc_id = ? AND rev_id = 1",
            (doc_id,),
        ).fetchone()
        assert row is not None
        stored_metadata = json.loads(row["metadata"])

        profile = stored_metadata["tokenizer_profile"]
        assert profile["canonical_tokenizer_id"]
        assert profile["canonical_tokenizer_version"]
        assert profile["canonical_mode"] in {"legacy_regex", "spacy", "deterministic_legal"}
        assert isinstance(profile["canonical_token_count"], int)
        assert profile["source_hash"] == (
            hashlib.sha256(body.encode("utf-8")).hexdigest()
        )
    finally:
        store.close()


def test_deterministic_legal_occurrences_emit_canonical_legal_atoms():
    from src.text.lexeme_index import collect_lexeme_occurrences

    text = "Civil Liability Act 2002 (NSW) s 5B(2)(a) Pt 4 Div 2 r 7.32 Sch 1 cl 4"
    occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
    assert [(occ.norm_text, occ.kind) for occ in occs] == [
        ("act:civil_liability_act_2002_nsw", "act_ref"),
        ("sec:5b", "section_ref"),
        ("subsec:2", "subsection_ref"),
        ("para:a", "paragraph_ref"),
        ("pt:4", "part_ref"),
        ("div:2", "division_ref"),
        ("rule:7.32", "rule_ref"),
        ("sch:1", "schedule_ref"),
        ("cl:4", "clause_ref"),
    ]


def test_deterministic_legal_occurrences_emit_gwb_style_acts_and_courts():
    from src.text.lexeme_index import collect_lexeme_occurrences

    text = (
        "Bush signed the Military Commissions Act of 2006. "
        "The ruling was vacated by the United States Court of Appeals for the Sixth Circuit "
        "before reaching the U.S. Supreme Court."
    )
    occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
    pairs = [(occ.norm_text, occ.kind) for occ in occs]
    assert ("act:military_commissions_act_of_2006", "act_ref") in pairs
    assert ("court:united_states_court_of_appeals_for_the_sixth_circuit", "court_ref") in pairs
    assert ("court:u_s_supreme_court", "court_ref") in pairs


def test_deterministic_legal_occurrences_emit_articles_constitutional_refs_and_instruments():
    from src.text.lexeme_index import collect_lexeme_occurrences

    text = (
        "Plaintiff S157/2002 v Commonwealth [2003] HCA 2 considered s 75(v) of the Constitution and Art 5. "
        "Later discussions referenced the India–United States Civil Nuclear Agreement and the U.S.–DPRK Agreed Framework."
    )
    occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
    pairs = [(occ.norm_text, occ.kind) for occ in occs]
    assert ("sec:75", "section_ref") in pairs
    assert ("para:v", "paragraph_ref") in pairs
    assert ("art:5", "article_ref") in pairs
    assert ("instrument:india_united_states_civil_nuclear_agreement", "instrument_ref") in pairs
    assert ("instrument:u_s_dprk_agreed_framework", "instrument_ref") in pairs


def test_deterministic_legal_occurrences_do_not_emit_article_ref_for_artful_or_gallery_cases():
    from src.text.lexeme_index import collect_lexeme_occurrences

    samples = [
        "Artful prose was a strength of GWB.",
        "The Art 5 gallery opened downtown.",
        "The label Art 5 was printed on the canvas.",
    ]
    for text in samples:
        occs = collect_lexeme_occurrences(text, canonical_mode="deterministic_legal")
        assert all(occ.kind != "article_ref" for occ in occs)
