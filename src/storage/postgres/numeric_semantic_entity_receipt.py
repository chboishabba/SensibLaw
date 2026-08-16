"""Portable canonical-entity leaves for numeric semantic receipts.

A document/corpus entity may be anchored to an object in another document. The
anchor therefore cannot be identified by the current document's object-id map or
by the historical object_digest (which contains dense local ids). Instead we
re-root it on a content-addressed document coordinate, source spans, stable
symbol digests, and token-support coordinates.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable, Mapping

from src.pnf.numeric_hyperfabric import numeric_digest


def _tag(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def _bytes(value: Any) -> bytes | None:
    return bytes(value) if value is not None else None


def portable_entity_leaves(
    cursor: Any,
    entity_ids: Iterable[int],
    *,
    object_leaves: Mapping[int, bytes],  # retained for call-surface compatibility
) -> dict[int, bytes]:
    del object_leaves
    ids = sorted({int(value) for value in entity_ids})
    if not ids:
        return {}
    cursor.execute(
        """
        SELECT entity.entity_id, entity.authority_class,
               canonical.symbol_digest,
               entity.authority_namespace, entity.authority_identifier,
               anchor.object_id,
               anchor_region.document_ref,
               anchor_region.region_kind,
               anchor_region.start_char, anchor_region.end_char,
               object_kind.symbol_digest, head.symbol_digest
          FROM execution.semantic_pnf_canonical_entity AS entity
          LEFT JOIN execution.semantic_symbol AS canonical
            ON canonical.symbol_id = entity.canonical_symbol_id
          LEFT JOIN execution.semantic_pnf_object AS anchor
            ON anchor.object_id = entity.anchor_object_id
          LEFT JOIN execution.semantic_pnf_region AS anchor_region
            ON anchor_region.region_id = anchor.region_id
          LEFT JOIN execution.semantic_symbol AS object_kind
            ON object_kind.symbol_id = anchor.object_kind_symbol_id
          LEFT JOIN execution.semantic_symbol AS head
            ON head.symbol_id = anchor.head_symbol_id
         WHERE entity.entity_id = ANY(%s)
        """,
        (ids,),
    )
    rows = tuple(cursor.fetchall())
    anchor_ids = [int(row[5]) for row in rows if row[5] is not None]
    support: dict[int, list[tuple[Any, ...]]] = {
        object_id: [] for object_id in anchor_ids
    }
    if anchor_ids:
        cursor.execute(
            """
            SELECT support.object_id, support.ordinal,
                   token.start_char, token.end_char,
                   lemma.symbol_digest, dependency.symbol_digest
              FROM execution.semantic_pnf_object_token_support AS support
              JOIN execution.semantic_parser_token AS token
                ON token.token_id = support.token_id
              LEFT JOIN execution.semantic_symbol AS lemma
                ON lemma.symbol_id = token.lemma_symbol_id
              LEFT JOIN execution.semantic_symbol AS dependency
                ON dependency.symbol_id = token.dependency_symbol_id
             WHERE support.object_id = ANY(%s)
             ORDER BY support.object_id, support.ordinal,
                      token.start_char, token.end_char
            """,
            (anchor_ids,),
        )
        for object_id, ordinal, start, end, lemma_digest, dependency_digest in cursor.fetchall():
            support[int(object_id)].append(
                (
                    int(ordinal), int(start), int(end),
                    _bytes(lemma_digest), _bytes(dependency_digest),
                )
            )

    result: dict[int, bytes] = {}
    for row in rows:
        entity_id = int(row[0])
        anchor_id = int(row[5]) if row[5] is not None else None
        anchor_leaf: bytes | None = None
        if anchor_id is not None:
            if row[6] is None or row[7] is None or row[8] is None or row[9] is None:
                raise RuntimeError("canonical entity anchor is missing source coordinates")
            anchor_leaf = numeric_digest(
                _tag("entity-anchor:v1"),
                _tag(str(row[6])),
                int(row[7]), int(row[8]), int(row[9]),
                _bytes(row[10]), _bytes(row[11]),
                tuple(support.get(anchor_id, ())),
            )
        namespace = str(row[3]) if row[3] is not None else None
        identifier = str(row[4]) if row[4] is not None else None
        if int(row[1]) == 4 and (namespace is None or identifier is None):
            raise RuntimeError("external canonical entity lacks authority coordinate")
        result[entity_id] = numeric_digest(
            _tag("entity:v1"),
            int(row[1]),
            _bytes(row[2]),
            anchor_leaf,
            _tag(namespace) if namespace is not None else None,
            _tag(identifier) if identifier is not None else None,
        )
    if len(result) != len(ids):
        raise RuntimeError("numeric semantic receipt could not resolve canonical entity")
    return result


__all__ = ["portable_entity_leaves"]
