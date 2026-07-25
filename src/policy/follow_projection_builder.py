"""Build generic follow projections from canonical PostgreSQL-bound artefacts.

The builder consumes factor/resolution/Domain-IR rows, not lane-owned nested graph
bundles.  AU and GWB profiles may filter relation families and label nodes, but
cannot alter identity, admissibility, or authority.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256
from src.policy.follow_projection import FollowProjection, build_follow_projection


def _refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _factor_node(row: Mapping[str, Any], ordinal: int) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    factor_ref = str(row.get("factor_ref") or "")
    factor_revision_ref = str(
        metadata.get("factor_revision_ref") or row.get("factor_revision_ref") or ""
    )
    return {
        "node_ref": "follow-node:" + canonical_sha256(
            {"factor_ref": factor_ref, "factor_revision_ref": factor_revision_ref}
        ),
        "node_kind": str(row.get("factor_type") or row.get("factor_type_ref") or "factor"),
        "label": str(
            metadata.get("canonical_label")
            or metadata.get("surface")
            or row.get("label")
            or factor_ref
        ),
        "factor_ref": factor_ref,
        "factor_revision_ref": factor_revision_ref or None,
        "assessment_ref": row.get("assessment_ref"),
        "admissibility_receipt_ref": row.get("admissibility_receipt_ref"),
        "resolution_ref": row.get("resolution_ref"),
        "domain_ir_ref": row.get("domain_ir_ref"),
        "source_revision_ref": row.get("source_revision_ref"),
        "ordinal": ordinal,
    }


def _relation_rows_from_factor(row: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    relations = metadata.get("follow_relations") or row.get("follow_relations") or ()
    if isinstance(relations, Mapping):
        relations = (relations,)
    return tuple(dict(value) for value in relations if isinstance(value, Mapping))


def build_follow_projection_from_canonical_rows(
    *,
    document_ref: str,
    profile_ref: str,
    scope_ref: str,
    projection_kind: str,
    factors: Sequence[Mapping[str, Any]],
    resolutions: Sequence[Mapping[str, Any]] = (),
    domain_ir: Sequence[Mapping[str, Any]] = (),
    relation_families: Iterable[str] = (),
    source_graph_ref: str | None = None,
) -> FollowProjection:
    allowed = set(_refs(relation_families))
    resolution_by_factor = {
        str(row.get("source_factor_ref") or row.get("fibre_summary_ref") or ""): row
        for row in resolutions
    }
    domain_ir_by_factor = {
        str(row.get("source_factor_ref") or ""): row for row in domain_ir
    }
    enriched: list[dict[str, Any]] = []
    for factor in factors:
        row = dict(factor)
        factor_ref = str(row.get("factor_ref") or "")
        resolution = resolution_by_factor.get(factor_ref, {})
        ir = domain_ir_by_factor.get(factor_ref, {})
        row["resolution_ref"] = resolution.get("resolution_ref")
        row["domain_ir_ref"] = ir.get("domain_ir_ref")
        row["assessment_ref"] = resolution.get("assessment_ref")
        row["admissibility_receipt_ref"] = resolution.get("admissibility_receipt_ref")
        enriched.append(row)
    node_rows = [_factor_node(row, index) for index, row in enumerate(enriched)]
    node_by_factor = {
        str(row.get("factor_ref") or ""): str(node["node_ref"])
        for row, node in zip(enriched, node_rows, strict=True)
    }
    edge_rows: list[dict[str, Any]] = []
    for factor in enriched:
        source_factor_ref = str(factor.get("factor_ref") or "")
        for relation in _relation_rows_from_factor(factor):
            relation_kind = str(
                relation.get("relation_kind") or relation.get("kind") or ""
            )
            if allowed and relation_kind not in allowed:
                continue
            target_factor_ref = str(
                relation.get("target_factor_ref") or relation.get("target_ref") or ""
            )
            source_node_ref = node_by_factor.get(source_factor_ref)
            target_node_ref = node_by_factor.get(target_factor_ref)
            if not source_node_ref or not target_node_ref:
                continue
            admissibility_state = str(
                relation.get("admissibility_state")
                or relation.get("decision")
                or "undetermined"
            )
            if admissibility_state == "promote":
                admissibility_state = "admitted"
            elif admissibility_state in {"audit", "abstain", "unknown"}:
                admissibility_state = "blocked"
            edge_identity = {
                "source_node_ref": source_node_ref,
                "target_node_ref": target_node_ref,
                "relation_kind": relation_kind,
                "profile_ref": profile_ref,
            }
            edge_rows.append(
                {
                    "edge_ref": "follow-edge:" + canonical_sha256(edge_identity),
                    "source_node_ref": source_node_ref,
                    "target_node_ref": target_node_ref,
                    "relation_kind": relation_kind,
                    "admissibility_state": admissibility_state,
                    "ordinal": len(edge_rows),
                    "evidence_refs": _refs(relation.get("evidence_refs") or ()),
                    "provenance_refs": _refs(
                        relation.get("provenance_refs")
                        or relation.get("source_refs")
                        or ()
                    ),
                    "admissibility_ground_refs": _refs(
                        relation.get("admissibility_ground_refs")
                        or relation.get("ground_refs")
                        or ()
                    ),
                }
            )
    source_resolution_ref = next(
        (
            str(row.get("resolution_ref") or "")
            for row in resolutions
            if str(row.get("resolution_ref") or "")
        ),
        None,
    )
    return build_follow_projection(
        document_ref=document_ref,
        profile_ref=profile_ref,
        scope_ref=scope_ref,
        projection_kind=projection_kind,
        node_rows=node_rows,
        edge_rows=edge_rows,
        source_graph_ref=source_graph_ref,
        source_resolution_ref=source_resolution_ref,
    )


__all__ = ["build_follow_projection_from_canonical_rows"]
