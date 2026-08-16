"""Enforce explicit dependency heads at the numeric sentence-closure boundary."""

from __future__ import annotations

from typing import Any

from src.pnf.numeric_operator_composition import NumericToken


_INSTALL_MARKER = "_numeric_head_integrity_execution_installed"


def install_numeric_head_integrity_execution() -> bool:
    from src.storage.postgres import numeric_hyperfabric_store as store

    if getattr(store, _INSTALL_MARKER, False):
        return False

    def load_sentence_tokens(cursor: Any, region_id: int) -> tuple[NumericToken, ...]:
        cursor.execute(
            """
            SELECT token.token_id,
                   token.orth_symbol_id,
                   token.lemma_symbol_id,
                   token.pos_symbol_id,
                   token.tag_symbol_id,
                   token.dependency_symbol_id,
                   token.head_token_id,
                   token.morph_set_id,
                   token.start_char,
                   token.end_char
              FROM execution.semantic_pnf_sentence_region AS link
              JOIN execution.semantic_parser_token AS token
                ON token.sentence_id = link.sentence_id
             WHERE link.region_id = %s
               AND token.representation_version = 2
             ORDER BY token.local_token_ordinal, token.token_id
            """,
            (region_id,),
        )
        rows = tuple(cursor.fetchall())
        if not rows:
            raise RuntimeError("numeric sentence region has no typed parser tokens")
        missing = [int(row[0]) for row in rows if row[6] is None]
        if missing:
            raise RuntimeError(
                "representation-v2 token is missing its explicit numeric head: "
                + ",".join(str(value) for value in missing[:8])
            )
        return tuple(
            NumericToken(
                token_id=int(row[0]),
                orth_id=int(row[1]),
                lemma_id=int(row[2]),
                pos_id=int(row[3]),
                tag_id=int(row[4]),
                dependency_id=int(row[5]),
                head_token_id=int(row[6]),
                morph_set_id=int(row[7]) if row[7] is not None else None,
                start_char=int(row[8]),
                end_char=int(row[9]),
            )
            for row in rows
        )

    store._load_sentence_tokens = load_sentence_tokens
    store._load_sentence_tokens_without_explicit_head_guard = getattr(
        store, "_load_sentence_tokens", None
    )
    setattr(store, _INSTALL_MARKER, True)
    return True


__all__ = ["install_numeric_head_integrity_execution"]
