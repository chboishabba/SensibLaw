"""Exact audit and candidate SQL for hierarchy-close admission pushdown.

The current hierarchy close is already child-local: it reads lookup rows only for
``child_interface_ids``. The measured inefficiency is later in the same local
pipeline: rows are grouped before the parent export-admission rule rejects many
of the grouped target fibres.

This module does not replace the production close yet. It makes the candidate
transformation executable and falsifiable:

    child lookup rows
    -> parent-export admission semi-join
    -> GROUP BY / min(rank)
    -> parent lookup

The admission predicate is exactly the existing migration-054 rule: a lookup row
is admissible iff the parent interface has an export with the same
``(target_kind, target_id)``. The parity audit compares the candidate grouped
relation with the already materialized parent lookup using two set differences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from src.runtime.optimization_economy import ConcentrationPoint, concentration_profile


PUSHDOWN_CONTRACT_REF = "sensiblaw.hierarchy-close-admission-pushdown.v0_1"

_GROUP_COLUMNS = "key_kind, key_a, key_b, target_kind, target_id"

PUSHDOWN_INSERT_SQL = f"""
INSERT INTO execution.semantic_pnf_interface_lookup
    (interface_id, key_kind, key_a, key_b, target_kind, target_id, rank)
SELECT %s,
       lookup.key_kind,
       lookup.key_a,
       lookup.key_b,
       lookup.target_kind,
       lookup.target_id,
       min(lookup.rank)
  FROM execution.semantic_pnf_interface_lookup AS lookup
 WHERE lookup.interface_id = ANY(%s)
   AND EXISTS (
       SELECT 1
         FROM execution.semantic_pnf_interface_export AS parent_export
        WHERE parent_export.interface_id = %s
          AND parent_export.target_kind = lookup.target_kind
          AND parent_export.target_id = lookup.target_id
   )
 GROUP BY {_GROUP_COLUMNS}
ON CONFLICT DO NOTHING
""".strip()


@dataclass(frozen=True, slots=True)
class ParentLookupPushdownAudit:
    parent_interface_id: int
    child_interface_count: int
    source_rows: int
    admitted_source_rows: int
    grouped_candidate_rows: int
    stored_parent_rows: int
    missing_candidate_rows: int
    excess_candidate_rows: int

    @property
    def exact_parity(self) -> bool:
        return self.missing_candidate_rows == 0 and self.excess_candidate_rows == 0

    @property
    def admission_selectivity(self) -> float | None:
        if self.source_rows == 0:
            return 0.0 if self.admitted_source_rows == 0 else None
        return self.admitted_source_rows / self.source_rows

    @property
    def grouping_input_reduction(self) -> float | None:
        selectivity = self.admission_selectivity
        return None if selectivity is None else 1.0 - selectivity

    @property
    def source_to_output_amplification(self) -> float | None:
        if self.stored_parent_rows == 0:
            return 0.0 if self.source_rows == 0 else None
        return self.source_rows / self.stored_parent_rows

    @property
    def admitted_to_output_amplification(self) -> float | None:
        if self.stored_parent_rows == 0:
            return 0.0 if self.admitted_source_rows == 0 else None
        return self.admitted_source_rows / self.stored_parent_rows

    def to_dict(self) -> dict[str, int | float | bool | None | str]:
        return {
            "contract_ref": PUSHDOWN_CONTRACT_REF,
            "parent_interface_id": self.parent_interface_id,
            "child_interface_count": self.child_interface_count,
            "source_rows": self.source_rows,
            "admitted_source_rows": self.admitted_source_rows,
            "grouped_candidate_rows": self.grouped_candidate_rows,
            "stored_parent_rows": self.stored_parent_rows,
            "missing_candidate_rows": self.missing_candidate_rows,
            "excess_candidate_rows": self.excess_candidate_rows,
            "exact_parity": self.exact_parity,
            "admission_selectivity": self.admission_selectivity,
            "grouping_input_reduction": self.grouping_input_reduction,
            "source_to_output_amplification": self.source_to_output_amplification,
            "admitted_to_output_amplification": self.admitted_to_output_amplification,
        }


def _scalar(cursor: Any, sql: str, parameters: tuple[Any, ...]) -> int:
    cursor.execute(sql, parameters)
    return int(cursor.fetchone()[0])


def audit_parent_lookup_pushdown(
    cursor: Any,
    *,
    parent_interface_id: int,
    child_interface_ids: Sequence[int],
) -> ParentLookupPushdownAudit:
    """Read-only exact parity/cardinality audit for one already-closed parent."""

    children = [int(value) for value in child_interface_ids]
    if not children:
        raise ValueError("parent lookup pushdown audit requires child interfaces")

    source_rows = _scalar(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_interface_lookup AS lookup
         WHERE lookup.interface_id = ANY(%s)
        """,
        (children,),
    )
    admitted_source_rows = _scalar(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_interface_lookup AS lookup
         WHERE lookup.interface_id = ANY(%s)
           AND EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_interface_export AS parent_export
                WHERE parent_export.interface_id = %s
                  AND parent_export.target_kind = lookup.target_kind
                  AND parent_export.target_id = lookup.target_id
           )
        """,
        (children, int(parent_interface_id)),
    )
    grouped_candidate_rows = _scalar(
        cursor,
        f"""
        SELECT count(*)
          FROM (
              SELECT {_GROUP_COLUMNS}, min(lookup.rank) AS rank
                FROM execution.semantic_pnf_interface_lookup AS lookup
               WHERE lookup.interface_id = ANY(%s)
                 AND EXISTS (
                     SELECT 1
                       FROM execution.semantic_pnf_interface_export AS parent_export
                      WHERE parent_export.interface_id = %s
                        AND parent_export.target_kind = lookup.target_kind
                        AND parent_export.target_id = lookup.target_id
                 )
               GROUP BY {_GROUP_COLUMNS}
          ) AS candidate
        """,
        (children, int(parent_interface_id)),
    )
    stored_parent_rows = _scalar(
        cursor,
        """
        SELECT count(*)
          FROM execution.semantic_pnf_interface_lookup
         WHERE interface_id = %s
        """,
        (int(parent_interface_id),),
    )

    candidate_relation = f"""
        SELECT {_GROUP_COLUMNS}, min(lookup.rank) AS rank
          FROM execution.semantic_pnf_interface_lookup AS lookup
         WHERE lookup.interface_id = ANY(%s)
           AND EXISTS (
               SELECT 1
                 FROM execution.semantic_pnf_interface_export AS parent_export
                WHERE parent_export.interface_id = %s
                  AND parent_export.target_kind = lookup.target_kind
                  AND parent_export.target_id = lookup.target_id
           )
         GROUP BY {_GROUP_COLUMNS}
    """
    stored_relation = f"""
        SELECT {_GROUP_COLUMNS}, rank
          FROM execution.semantic_pnf_interface_lookup
         WHERE interface_id = %s
    """
    missing_candidate_rows = _scalar(
        cursor,
        f"SELECT count(*) FROM (({stored_relation}) EXCEPT ({candidate_relation})) AS missing",
        (int(parent_interface_id), children, int(parent_interface_id)),
    )
    excess_candidate_rows = _scalar(
        cursor,
        f"SELECT count(*) FROM (({candidate_relation}) EXCEPT ({stored_relation})) AS excess",
        (children, int(parent_interface_id), int(parent_interface_id)),
    )

    return ParentLookupPushdownAudit(
        parent_interface_id=int(parent_interface_id),
        child_interface_count=len(children),
        source_rows=source_rows,
        admitted_source_rows=admitted_source_rows,
        grouped_candidate_rows=grouped_candidate_rows,
        stored_parent_rows=stored_parent_rows,
        missing_candidate_rows=missing_candidate_rows,
        excess_candidate_rows=excess_candidate_rows,
    )


__all__ = [
    "ConcentrationPoint",
    "PUSHDOWN_CONTRACT_REF",
    "PUSHDOWN_INSERT_SQL",
    "ParentLookupPushdownAudit",
    "audit_parent_lookup_pushdown",
    "concentration_profile",
]
