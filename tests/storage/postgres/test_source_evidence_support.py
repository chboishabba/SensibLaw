from __future__ import annotations

from dataclasses import dataclass

from src.pnf.packed_sentence_fibre import PackedSentenceFibre, PackedSourceToken
from src.storage.postgres.source_evidence_support import (
    ensure_source_evidence_support_schema,
    source_evidence_rows,
)


class _Cursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str, params=None) -> None:
        self.statements.append(statement)


def _fibre() -> PackedSentenceFibre:
    token = PackedSourceToken(
        local_id=0,
        evidence_digest=b"e" * 32,
        ordinal=0,
        start_char=3,
        end_char=8,
        start_byte=3,
        end_byte=8,
        orth="party",
        lemma="party",
        pos="NOUN",
        tag="NOUN",
        dependency="ROOT",
        head_local_id=0,
        morphology=(),
    )
    return PackedSentenceFibre(
        sentence_digest=b"s" * 32,
        ordinal=0,
        start_char=3,
        end_char=8,
        start_byte=3,
        end_byte=8,
        tokens=(token,),
    )


def test_g4_schema_has_no_parser_token_foreign_key() -> None:
    cursor = _Cursor()
    receipt = ensure_source_evidence_support_schema(cursor)
    ddl = "\n".join(cursor.statements)
    assert receipt.parser_token_foreign_keys == 0
    assert receipt.authoritative_identity == "evidence_digest"
    assert "semantic_source_token_evidence" in ddl
    assert "semantic_pnf_object_evidence_support" in ddl
    assert "semantic_pnf_factor_evidence_support" in ddl
    assert "semantic_parser_token" not in ddl


def test_source_evidence_rows_preserve_full_digest_and_coordinates() -> None:
    rows = source_evidence_rows(_fibre())
    assert rows == (
        rows[0].__class__(
            evidence_digest=b"e" * 32,
            sentence_digest=b"s" * 32,
            token_ordinal=0,
            start_char=3,
            end_char=8,
            start_byte=3,
            end_byte=8,
        ),
    )
