"""Corpus-wide numeric symbol and morphology interning.

Text exists only at this boundary. The returned ids are the sole parser/PNF
execution representation and are stable across documents in the same database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import unicodedata
from typing import Any

from src.pnf.numeric_hyperfabric import SymbolKind, numeric_digest, symbol_digest


@dataclass(frozen=True, slots=True)
class SymbolValue:
    kind: SymbolKind
    text: str

    @property
    def normalized_text(self) -> str:
        return normalize_symbol(self.kind, self.text)


def normalize_symbol(kind: SymbolKind, text: str) -> str:
    value = unicodedata.normalize("NFC", str(text or ""))
    if kind in {
        SymbolKind.LEMMA,
        SymbolKind.DEPENDENCY,
        SymbolKind.PREDICATE,
        SymbolKind.ROLE,
        SymbolKind.RESIDUAL_TYPE,
        SymbolKind.OBJECT_KIND,
        SymbolKind.DEFINITION,
        SymbolKind.SCOPE,
        SymbolKind.TEMPORAL,
        SymbolKind.MODAL,
        SymbolKind.GRAMMATICAL,
    }:
        return value.casefold()
    if kind in {
        SymbolKind.POS,
        SymbolKind.TAG,
        SymbolKind.ENTITY_TYPE,
        SymbolKind.MORPH_FEATURE,
    }:
        return value.upper()
    return value


def _temporary_name(prefix: str) -> str:
    return f"tmp_{prefix}"


def intern_symbols(
    cursor: Any,
    values: Iterable[SymbolValue | tuple[SymbolKind, str]],
) -> dict[tuple[SymbolKind, str], int]:
    normalized: dict[tuple[SymbolKind, str], bytes] = {}
    for value in values:
        if isinstance(value, SymbolValue):
            kind = value.kind
            text = value.normalized_text
        else:
            kind = SymbolKind(value[0])
            text = normalize_symbol(kind, value[1])
        normalized[(kind, text)] = symbol_digest(kind, text)
    if not normalized:
        return {}

    temporary = _temporary_name("semantic_symbol_input")
    cursor.execute(f"DROP TABLE IF EXISTS {temporary}")
    cursor.execute(
        f"""
        CREATE TEMP TABLE {temporary} (
            kind_id SMALLINT NOT NULL,
            symbol_text TEXT NOT NULL,
            symbol_digest BYTEA NOT NULL,
            PRIMARY KEY (kind_id, symbol_text)
        ) ON COMMIT DROP
        """
    )
    with cursor.copy(
        f"COPY {temporary} (kind_id, symbol_text, symbol_digest) FROM STDIN"
    ) as copy:
        for (kind, text), digest in sorted(
            normalized.items(),
            key=lambda item: (int(item[0][0]), item[0][1]),
        ):
            copy.write_row((int(kind), text, digest))
    cursor.execute(
        f"""
        INSERT INTO execution.semantic_symbol
            (kind_id, symbol_text, symbol_digest)
        SELECT kind_id, symbol_text, symbol_digest
          FROM {temporary}
        ON CONFLICT (kind_id, symbol_text) DO NOTHING
        """
    )
    cursor.execute(
        f"""
        SELECT symbol.kind_id, symbol.symbol_text, symbol.symbol_id
          FROM execution.semantic_symbol AS symbol
          JOIN {temporary} AS requested
            ON requested.kind_id = symbol.kind_id
           AND requested.symbol_text = symbol.symbol_text
        ORDER BY symbol.kind_id, symbol.symbol_text
        """
    )
    result = {
        (SymbolKind(int(kind_id)), str(text)): int(symbol_id)
        for kind_id, text, symbol_id in cursor.fetchall()
    }
    if len(result) != len(normalized):
        raise RuntimeError("numeric symbol interning returned an incomplete mapping")
    return result


def symbol_id(
    mapping: Mapping[tuple[SymbolKind, str], int],
    kind: SymbolKind,
    text: str,
) -> int:
    key = (kind, normalize_symbol(kind, text))
    try:
        return int(mapping[key])
    except KeyError as error:
        raise KeyError(
            f"symbol was not interned: kind={int(kind)} text={key[1]!r}"
        ) from error


def intern_morph_sets(
    cursor: Any,
    sets: Sequence[Sequence[tuple[int, int]]],
) -> dict[tuple[tuple[int, int], ...], int]:
    """Intern one bounded morphology fibre with two set-wise SQL projections.

    The canonical input is already a finite relation of morph-set digests and
    numeric feature/value members. Do not decompose that relation into one INSERT
    per set followed by one ``executemany`` per member family. PostgreSQL UNNEST
    preserves the batch directly without introducing another temporary schema.
    """

    canonical_sets = {
        tuple(sorted({(int(feature), int(value)) for feature, value in members}))
        for members in sets
    }
    canonical_sets.discard(())
    if not canonical_sets:
        return {}

    digests = {
        members: numeric_digest(
            int(SymbolKind.MORPH_FEATURE),
            tuple(item for pair in members for item in pair),
        )
        for members in canonical_sets
    }
    ordered_sets = tuple(sorted(digests.items(), key=lambda item: item[1]))
    set_digests = [digest for _members, digest in ordered_sets]
    member_counts = [len(members) for members, _digest in ordered_sets]

    cursor.execute(
        """
        WITH input AS (
            SELECT *
              FROM unnest(%s::BYTEA[], %s::SMALLINT[])
                   AS row(morph_digest, member_count)
        )
        INSERT INTO execution.semantic_morph_set
            (morph_digest, member_count)
        SELECT morph_digest, member_count
          FROM input
        ON CONFLICT (morph_digest) DO NOTHING
        """,
        (set_digests, member_counts),
    )

    member_digest: list[bytes] = []
    member_ordinal: list[int] = []
    member_feature: list[int] = []
    member_value: list[int] = []
    for members, digest in ordered_sets:
        for ordinal, (feature_id, value_id) in enumerate(members):
            member_digest.append(digest)
            member_ordinal.append(ordinal)
            member_feature.append(feature_id)
            member_value.append(value_id)

    cursor.execute(
        """
        WITH member_input AS (
            SELECT *
              FROM unnest(
                  %s::BYTEA[],
                  %s::SMALLINT[],
                  %s::BIGINT[],
                  %s::BIGINT[]
              ) AS row(
                  morph_digest,
                  ordinal,
                  feature_symbol_id,
                  value_symbol_id
              )
        )
        INSERT INTO execution.semantic_morph_set_member
            (morph_set_id, ordinal, feature_symbol_id, value_symbol_id)
        SELECT morph.morph_set_id,
               member.ordinal,
               member.feature_symbol_id,
               member.value_symbol_id
          FROM member_input AS member
          JOIN execution.semantic_morph_set AS morph
            ON morph.morph_digest = member.morph_digest
        ON CONFLICT DO NOTHING
        """,
        (member_digest, member_ordinal, member_feature, member_value),
    )

    cursor.execute(
        """
        SELECT morph_set_id, morph_digest
          FROM execution.semantic_morph_set
         WHERE morph_digest = ANY(%s)
        """,
        (set_digests,),
    )
    by_digest = {
        bytes(digest): int(morph_set_id) for morph_set_id, digest in cursor.fetchall()
    }
    result: dict[tuple[tuple[int, int], ...], int] = {}
    for members, digest in ordered_sets:
        morph_set_id = by_digest.get(digest)
        if morph_set_id is None:
            raise RuntimeError("numeric morphology interning lost a set")
        result[members] = morph_set_id
    return result


def load_symbol_texts(
    cursor: Any,
    symbol_ids: Iterable[int],
) -> dict[int, str]:
    ids = sorted({int(value) for value in symbol_ids if int(value) > 0})
    if not ids:
        return {}
    cursor.execute(
        """
        SELECT symbol_id, symbol_text
          FROM execution.semantic_symbol
         WHERE symbol_id = ANY(%s)
        """,
        (ids,),
    )
    return {int(symbol_id): str(text) for symbol_id, text in cursor.fetchall()}


__all__ = [
    "SymbolValue",
    "intern_morph_sets",
    "intern_symbols",
    "load_symbol_texts",
    "normalize_symbol",
    "symbol_id",
]
