"""Exact operational-demand occurrence persistence into PostgreSQL.

The operational factor carrier uses immutable ``parser-token:...`` references.
The numeric parser authority uses a different database-local token identity, so
this boundary recovers only the token's canonical document coordinates.  The
later SQL projection selects a concrete numeric parser run and demand, failing
closed if more than one survives.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.policy.carriers.canonical import canonical_sha256


_OCCURRENCE_ROLE_ID = {"trigger": 1, "target": 2, "evidence": 3}


def numeric_parser_token_coordinate_map(
    cursor: Any, *, document_ref: str
) -> dict[str, tuple[int, int]]:
    """Reconstruct operational parser-token refs from exact numeric coordinates.

    ``parser_index`` is the authored token order over the document.  Multiple
    numeric parser runs may contain the same coordinates; they intentionally
    collapse here because run selection happens later against the exact numeric
    demand.  No token text participates in the mapping.
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

    Unknown/non-token provenance is ignored rather than guessed.  A demand can
    therefore persist successfully with zero occurrence rows; that state remains
    unresolved and cannot authorize H9.
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
        coordinate = coordinate_map.get(token_ref)
        if role_id is None or not residual_type or coordinate is None or not document_ref:
            continue
        start_char, end_char = coordinate
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
            ) DO NOTHING
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

    # Projection is idempotent and fail-closed.  It may return zero when the
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
