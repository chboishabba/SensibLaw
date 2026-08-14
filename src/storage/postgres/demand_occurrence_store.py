"""Exact operational-demand occurrence persistence into PostgreSQL.

The operational factor carrier uses immutable ``parser-token:...`` references.
The numeric parser authority uses a different database-local token identity, so
this boundary optionally recovers the token's canonical document coordinates.
The immutable operational occurrence is persisted even when that numeric tape
is not available yet; later replay may fill the coordinates and project it.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


_OCCURRENCE_ROLE_ID = {"trigger": 1, "target": 2, "evidence": 3}


def numeric_parser_token_coordinate_map(
    cursor: Any, *, document_ref: str
) -> dict[str, tuple[int, int]]:
    """Reconstruct operational parser-token refs from exact numeric coordinates.

    ``parser_index`` is the authored token order over the document. Multiple
    numeric parser runs may contain the same coordinates; they intentionally
    collapse here because run selection happens later against the exact numeric
    demand. No token text participates in the mapping.
    """

    cursor.execute(
        """
        SELECT DISTINCT token.start_char, token.end_char
          FROM execution.semantic_parser_token AS token
         WHERE token.document_ref = %s
           AND token.representation_version = 2
         ORDER BY token.start_char, token.end_char
        """,
        (document_ref,),
    )
    coordinates = tuple((int(row[0]), int(row[1])) for row in cursor.fetchall())
    return {
        "parser-token:"
        + canonical_sha256(
            {
                "document_ref": document_ref,
                "parser_index": parser_index,
                "start": start_char,
                "end": end_char,
            }
        ): (start_char, end_char)
        for parser_index, (start_char, end_char) in enumerate(coordinates)
    }


def persist_resolution_demand_occurrences(
    cursor: Any,
    *,
    demand: Mapping[str, Any],
    coordinate_map: Mapping[str, tuple[int, int]],
) -> int:
    """Persist producer-authored occurrences and project them to numeric PNF.

    A missing numeric coordinate does not erase the producer observation. It is
    persisted with NULL coordinates and remains non-projectable until a later
    replay can recover the exact parser coordinate. Unknown semantic roles are
    ignored rather than guessed.
    """

    demand_ref = str(demand["demand_ref"])
    document_ref = str(
        demand.get("document_scope")
        or demand.get("scope_ref")
        or demand.get("document_ref")
        or ""
    )
    inserted = 0
    for occurrence in demand.get("occurrence_provenance") or ():
        if not isinstance(occurrence, Mapping):
            continue
        role_name = str(occurrence.get("occurrence_role") or "")
        role_id = _OCCURRENCE_ROLE_ID.get(role_name)
        token_ref = str(occurrence.get("parser_token_ref") or "")
        residual_type = str(occurrence.get("residual_type") or "")
        if role_id is None or not token_ref or not residual_type or not document_ref:
            continue
        coordinate = coordinate_map.get(token_ref)
        start_char = coordinate[0] if coordinate is not None else None
        end_char = coordinate[1] if coordinate is not None else None
        cursor.execute(
            """
            INSERT INTO resolution.demand_occurrence_provenance
                (demand_ref,residual_type_ref,occurrence_role,
                 parser_token_ref,document_ref,start_char,end_char,
                 semantic_role_ref,ordinal,producer_ref)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (
                demand_ref,residual_type_ref,occurrence_role,
                parser_token_ref,ordinal
            ) DO UPDATE SET
                start_char=COALESCE(
                    resolution.demand_occurrence_provenance.start_char,
                    EXCLUDED.start_char
                ),
                end_char=COALESCE(
                    resolution.demand_occurrence_provenance.end_char,
                    EXCLUDED.end_char
                )
            """,
            (
                demand_ref,
                residual_type,
                role_id,
                token_ref,
                document_ref,
                start_char,
                end_char,
                occurrence.get("semantic_role"),
                int(occurrence.get("ordinal") or 0),
                str(occurrence.get("producer_ref") or "operational-demand:v1"),
            ),
        )
        inserted += int(cursor.rowcount or 0)

    # Projection is idempotent and fail-closed. It may return zero when the
    # numeric demand carrier has not yet been built or when historical runs are
    # ambiguous; neither case is negative semantic evidence.
    cursor.execute(
        "SELECT execution.project_resolution_demand_occurrence_to_numeric_pnf(%s)",
        (demand_ref,),
    )
    cursor.fetchone()
    return inserted


__all__ = [
    "numeric_parser_token_coordinate_map",
    "persist_resolution_demand_occurrences",
]
