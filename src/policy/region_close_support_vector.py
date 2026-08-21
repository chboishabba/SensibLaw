"""Diagnostic semantic-support vector for genuine numeric region closes.

The close EXPLAIN tells us *how long* each trigger takes.  This companion probe
records the semantic population that could plausibly explain that cost without
using close ordinal as a proxy for state size.

It is deliberately diagnostic-only and is called only for explicitly selected
live close probes.  The counts therefore do not become production compiler work
or semantic authority.  They execute before the measured close UPDATE, so their
own query time is outside PostgreSQL's reported EXPLAIN Execution Time.
"""

from __future__ import annotations

from typing import Any, Mapping


REGION_CLOSE_SUPPORT_VECTOR_REF = "sensiblaw.region-close-support-vector.v0_1"


def capture_region_close_support_vector(
    cursor: Any,
    *,
    preclose: Mapping[str, Any],
) -> dict[str, int | str]:
    """Capture local support and document-population controls before one close.

    The local coordinates intentionally mirror the current trigger definitions:

    * adjacency searches only locally-closed siblings with the same canonical
      parent and region kind, selecting at most one neighbour on either side;
    * anaphor projection consumes representation-v2 pronoun tokens in the
      closing sentence fibre.

    Document-level counts are controls, not claims that those rows are touched
    by the close.  A later analysis can therefore test local-support correlation
    separately from accumulated-carrier correlation.
    """

    run_ref = str(preclose["run_ref"])
    document_ref = str(preclose["document_ref"])
    region_id = int(preclose["region_id"])
    region_kind = int(preclose["region_kind"])
    parent_region_id = preclose.get("parent_region_id")
    start_char = int(preclose["start_char"])
    end_char = int(preclose["end_char"])

    cursor.execute(
        """
        SELECT
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS region
              WHERE region.run_ref=%s
                AND region.document_ref=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS region
              WHERE region.run_ref=%s
                AND region.document_ref=%s
                AND region.closure_state IN (2,3)),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS region
              WHERE region.run_ref=%s
                AND region.document_ref=%s
                AND region.region_kind=1),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS region
              WHERE region.run_ref=%s
                AND region.document_ref=%s
                AND region.region_kind IN (2,4)),
            (SELECT count(*)
               FROM execution.semantic_pnf_interface AS interface
               JOIN execution.semantic_pnf_region AS region
                 ON region.region_id=interface.region_id
              WHERE region.run_ref=%s
                AND region.document_ref=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_demand AS demand
               JOIN execution.semantic_pnf_region AS region
                 ON region.region_id=demand.source_region_id
              WHERE region.run_ref=%s
                AND region.document_ref=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_mention AS mention
               JOIN execution.semantic_pnf_region AS region
                 ON region.region_id=mention.region_id
              WHERE region.run_ref=%s
                AND region.document_ref=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS sibling
              WHERE sibling.run_ref=%s
                AND sibling.document_ref=%s
                AND sibling.region_kind=%s
                AND sibling.parent_region_id IS NOT DISTINCT FROM %s
                AND sibling.closure_state IN (2,3)
                AND sibling.region_id<>%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_sentence_region AS link
               JOIN execution.semantic_parser_token AS token
                 ON token.sentence_id=link.sentence_id
              WHERE link.region_id=%s
                AND token.representation_version=2),
            (SELECT count(*)
               FROM execution.semantic_pnf_sentence_region AS link
               JOIN execution.semantic_parser_token AS token
                 ON token.sentence_id=link.sentence_id
                AND token.representation_version=2
               JOIN execution.semantic_pnf_anaphor_projection_constant AS constant
                 ON constant.singleton
                AND token.pos_symbol_id=constant.pronoun_pos_symbol_id
              WHERE link.region_id=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_demand AS demand
              WHERE demand.source_region_id=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_mention AS mention
              WHERE mention.region_id=%s
                AND mention.active),
            (SELECT count(*)
               FROM execution.semantic_pnf_interface AS interface
               JOIN execution.semantic_pnf_interface_export AS export
                 ON export.interface_id=interface.interface_id
              WHERE interface.region_id=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS sibling
              WHERE sibling.run_ref=%s
                AND sibling.document_ref=%s
                AND sibling.region_kind=%s
                AND sibling.parent_region_id IS NOT DISTINCT FROM %s
                AND sibling.closure_state IN (2,3)
                AND sibling.region_id<>%s
                AND sibling.end_char<=%s),
            (SELECT count(*)
               FROM execution.semantic_pnf_region AS sibling
              WHERE sibling.run_ref=%s
                AND sibling.document_ref=%s
                AND sibling.region_kind=%s
                AND sibling.parent_region_id IS NOT DISTINCT FROM %s
                AND sibling.closure_state IN (2,3)
                AND sibling.region_id<>%s
                AND sibling.start_char>=%s)
        """,
        (
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            run_ref,
            document_ref,
            region_kind,
            parent_region_id,
            region_id,
            region_id,
            region_id,
            region_id,
            region_id,
            region_id,
            run_ref,
            document_ref,
            region_kind,
            parent_region_id,
            region_id,
            start_char,
            run_ref,
            document_ref,
            region_kind,
            parent_region_id,
            region_id,
            end_char,
        ),
    )
    row = cursor.fetchone()
    if row is None or len(row) != 15:
        raise RuntimeError("region-close support probe returned an invalid carrier vector")

    values = tuple(int(value) for value in row)
    left_available = int(values[13] > 0)
    right_available = int(values[14] > 0)
    return {
        "contract_ref": REGION_CLOSE_SUPPORT_VECTOR_REF,
        "document_region_count": values[0],
        "document_closed_region_count": values[1],
        "document_sentence_region_count": values[2],
        "document_adjacent_region_count": values[3],
        "document_interface_count": values[4],
        "document_demand_count": values[5],
        "document_mention_count": values[6],
        "same_parent_closed_sibling_count": values[7],
        "local_token_count": values[8],
        "local_pronoun_token_count": values[9],
        "local_demand_count": values[10],
        "local_active_mention_count": values[11],
        "local_interface_export_count": values[12],
        "closed_left_sibling_count": values[13],
        "closed_right_sibling_count": values[14],
        "adjacent_candidate_side_count": left_available + right_available,
        "semantics": (
            "pre-close diagnostic counts; local fields approximate current trigger "
            "support while document fields are accumulated-state controls"
        ),
    }


__all__ = [
    "REGION_CLOSE_SUPPORT_VECTOR_REF",
    "capture_region_close_support_vector",
]
