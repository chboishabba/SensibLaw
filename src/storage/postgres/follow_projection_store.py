"""PostgreSQL persistence/query boundary for generic follow projections.

The store is fail-closed: it validates all durable parents and never creates
missing PNF factors, assessments, resolutions, Domain IR, or source revisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from src.policy.follow_projection import FollowProjection


def _existing_refs(cursor: Any, table: str, column: str, refs: Iterable[str]) -> set[str]:
    values = tuple(sorted({str(value) for value in refs if str(value)}))
    if not values:
        return set()
    cursor.execute(f"SELECT {column} FROM {table} WHERE {column} = ANY(%s)", (list(values),))
    return {str(row[0]) for row in cursor.fetchall()}


def _require_subset(label: str, requested: Iterable[str], existing: set[str]) -> None:
    missing = sorted({str(value) for value in requested if str(value)} - existing)
    if missing:
        raise ValueError(f"follow projection has non-durable {label}: {missing}")


def validate_follow_projection_parents(cursor: Any, projection: FollowProjection) -> None:
    factor_refs = {row.factor_ref for row in projection.nodes if row.factor_ref}
    factor_revision_refs = {row.factor_revision_ref for row in projection.nodes if row.factor_revision_ref}
    assessment_refs = {row.assessment_ref for row in projection.nodes if row.assessment_ref}
    admission_refs = {
        row.admissibility_receipt_ref for row in projection.nodes if row.admissibility_receipt_ref
    }
    resolution_refs = {row.resolution_ref for row in projection.nodes if row.resolution_ref}
    domain_ir_refs = {row.domain_ir_ref for row in projection.nodes if row.domain_ir_ref}

    # Factor tables are canonical algebra tables in the PostgreSQL spine.
    _require_subset(
        "factor refs",
        factor_refs,
        _existing_refs(cursor, "algebra.factor", "factor_ref", factor_refs),
    )
    _require_subset(
        "factor revision refs",
        factor_revision_refs,
        _existing_refs(
            cursor, "algebra.factor_revision", "factor_revision_ref", factor_revision_refs
        ),
    )
    _require_subset(
        "candidate assessment refs",
        assessment_refs,
        _existing_refs(
            cursor, "pnf_candidate_assessment", "assessment_ref", assessment_refs
        ),
    )
    _require_subset(
        "admissibility receipt refs",
        admission_refs,
        _existing_refs(
            cursor, "pnf_admissibility_receipt", "receipt_ref", admission_refs
        ),
    )
    _require_subset(
        "resolution refs",
        resolution_refs,
        _existing_refs(cursor, "pnf_resolution_receipt", "resolution_ref", resolution_refs),
    )
    _require_subset(
        "Domain IR refs",
        domain_ir_refs,
        _existing_refs(cursor, "pnf_domain_ir", "domain_ir_ref", domain_ir_refs),
    )
    if projection.source_resolution_ref:
        _require_subset(
            "source resolution ref",
            (projection.source_resolution_ref,),
            _existing_refs(
                cursor,
                "pnf_resolution_receipt",
                "resolution_ref",
                (projection.source_resolution_ref,),
            ),
        )


def persist_follow_projection(cursor: Any, projection: FollowProjection) -> str:
    validate_follow_projection_parents(cursor, projection)
    cursor.execute(
        """
        INSERT INTO pnf_follow_projection
            (projection_ref, document_ref, profile_ref, scope_ref,
             projection_kind, source_graph_ref, source_resolution_ref,
             derived_only, challengeable, promotes_truth, execution_authority)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, FALSE, FALSE)
        ON CONFLICT (projection_ref) DO NOTHING
        """,
        (
            projection.projection_ref,
            projection.document_ref,
            projection.profile_ref,
            projection.scope_ref,
            projection.projection_kind,
            projection.source_graph_ref,
            projection.source_resolution_ref,
        ),
    )
    if projection.nodes:
        cursor.executemany(
            """
            INSERT INTO pnf_follow_node
                (node_ref, projection_ref, node_kind, label, factor_ref,
                 factor_revision_ref, assessment_ref, admissibility_receipt_ref,
                 resolution_ref, domain_ir_ref, source_revision_ref, ordinal,
                 derived_only)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (node_ref) DO NOTHING
            """,
            [
                (
                    node.node_ref,
                    projection.projection_ref,
                    node.node_kind,
                    node.label,
                    node.factor_ref,
                    node.factor_revision_ref,
                    node.assessment_ref,
                    node.admissibility_receipt_ref,
                    node.resolution_ref,
                    node.domain_ir_ref,
                    node.source_revision_ref,
                    node.ordinal,
                )
                for node in sorted(projection.nodes, key=lambda value: (value.ordinal, value.node_ref))
            ],
        )
    if projection.edges:
        cursor.executemany(
            """
            INSERT INTO pnf_follow_edge
                (edge_ref, projection_ref, source_node_ref, target_node_ref,
                 relation_kind, admissibility_state, ordinal, derived_only,
                 challengeable, promotes_truth, execution_authority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, FALSE, FALSE)
            ON CONFLICT (edge_ref) DO NOTHING
            """,
            [
                (
                    edge.edge_ref,
                    projection.projection_ref,
                    edge.source_node_ref,
                    edge.target_node_ref,
                    edge.relation_kind,
                    edge.admissibility_state,
                    edge.ordinal,
                )
                for edge in sorted(projection.edges, key=lambda value: (value.ordinal, value.edge_ref))
            ],
        )
        evidence_rows = [
            (edge.edge_ref, ref, "support", ordinal)
            for edge in projection.edges
            for ordinal, ref in enumerate(edge.evidence_refs)
        ]
        provenance_rows = [
            (edge.edge_ref, ref, "source", ordinal)
            for edge in projection.edges
            for ordinal, ref in enumerate(edge.provenance_refs)
        ]
        ground_rows = [
            (edge.edge_ref, ref, "admissibility", ordinal)
            for edge in projection.edges
            for ordinal, ref in enumerate(edge.admissibility_ground_refs)
        ]
        if evidence_rows:
            cursor.executemany(
                """
                INSERT INTO pnf_follow_edge_evidence
                    (edge_ref, evidence_ref, evidence_role, ordinal)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                evidence_rows,
            )
        if provenance_rows:
            cursor.executemany(
                """
                INSERT INTO pnf_follow_edge_provenance
                    (edge_ref, provenance_ref, provenance_role, ordinal)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                provenance_rows,
            )
        if ground_rows:
            cursor.executemany(
                """
                INSERT INTO pnf_follow_edge_admissibility_ground
                    (edge_ref, ground_ref, ground_kind, ordinal)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                """,
                ground_rows,
            )
    return projection.projection_ref


@dataclass(frozen=True)
class FollowProjectionQueryResult:
    projection: Mapping[str, Any]
    nodes: tuple[Mapping[str, Any], ...]
    edges: tuple[Mapping[str, Any], ...]
    evidence: tuple[Mapping[str, Any], ...]
    provenance: tuple[Mapping[str, Any], ...]
    admissibility_grounds: tuple[Mapping[str, Any], ...]

    def presentation_payload(self) -> dict[str, Any]:
        """Detached endpoint data; never accepted as semantic input."""
        return {
            "projection": dict(self.projection),
            "nodes": [dict(row) for row in self.nodes],
            "edges": [dict(row) for row in self.edges],
            "edge_evidence": [dict(row) for row in self.evidence],
            "edge_provenance": [dict(row) for row in self.provenance],
            "admissibility_grounds": [dict(row) for row in self.admissibility_grounds],
            "presentation_only": True,
            "semantic_input_allowed": False,
        }


def _rows(cursor: Any) -> tuple[dict[str, Any], ...]:
    columns = [value.name for value in cursor.description]
    return tuple(dict(zip(columns, row, strict=True)) for row in cursor.fetchall())


def query_follow_projection(cursor: Any, projection_ref: str) -> FollowProjectionQueryResult:
    cursor.execute(
        """
        SELECT projection_ref, document_ref, profile_ref, scope_ref,
               projection_kind, source_graph_ref, source_resolution_ref,
               derived_only, challengeable, promotes_truth, execution_authority
        FROM pnf_follow_projection WHERE projection_ref = %s
        """,
        (projection_ref,),
    )
    projection_rows = _rows(cursor)
    if len(projection_rows) != 1:
        raise LookupError(f"unknown follow projection: {projection_ref}")
    cursor.execute(
        "SELECT * FROM pnf_follow_projection_rows WHERE projection_ref = %s ORDER BY node_ordinal, node_ref",
        (projection_ref,),
    )
    nodes = _rows(cursor)
    cursor.execute(
        "SELECT * FROM pnf_follow_edge_rows WHERE projection_ref = %s ORDER BY edge_ordinal, edge_ref",
        (projection_ref,),
    )
    edges = _rows(cursor)
    edge_refs = [str(row["edge_ref"]) for row in edges]
    if edge_refs:
        cursor.execute(
            "SELECT edge_ref, evidence_ref, evidence_role, ordinal FROM pnf_follow_edge_evidence WHERE edge_ref = ANY(%s) ORDER BY edge_ref, ordinal",
            (edge_refs,),
        )
        evidence = _rows(cursor)
        cursor.execute(
            "SELECT edge_ref, provenance_ref, provenance_role, ordinal FROM pnf_follow_edge_provenance WHERE edge_ref = ANY(%s) ORDER BY edge_ref, ordinal",
            (edge_refs,),
        )
        provenance = _rows(cursor)
        cursor.execute(
            "SELECT edge_ref, ground_ref, ground_kind, ordinal FROM pnf_follow_edge_admissibility_ground WHERE edge_ref = ANY(%s) ORDER BY edge_ref, ordinal",
            (edge_refs,),
        )
        grounds = _rows(cursor)
    else:
        evidence = provenance = grounds = ()
    return FollowProjectionQueryResult(
        projection=projection_rows[0],
        nodes=nodes,
        edges=edges,
        evidence=evidence,
        provenance=provenance,
        admissibility_grounds=grounds,
    )


__all__ = [
    "FollowProjectionQueryResult",
    "persist_follow_projection",
    "query_follow_projection",
    "validate_follow_projection_parents",
]
