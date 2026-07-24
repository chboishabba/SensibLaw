"""Bind reduced fibre summaries to durable PNF factor coordinates for projection.

A reduced summary is the semantic lifecycle coordinate. Existing base proposals
may point to a pre-existing PNF factor through ``source_factor_ref``; Domain IR
must use that durable factor ref for resolution demands and persistence while
retaining the reduced summary ref in metadata.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def bind_projection_factor_rows(
    *,
    reduced_factors: Sequence[Mapping[str, Any]],
    proposals: Sequence[Mapping[str, Any]],
    graph_factors: Sequence[Any],
) -> tuple[Mapping[str, Any], ...]:
    proposal_by_ref = {
        str(row.get("proposal_ref") or ""): row
        for row in proposals
        if row.get("proposal_ref")
    }
    graph_rows = tuple(
        row.to_dict() if hasattr(row, "to_dict") else dict(row)
        for row in graph_factors
    )
    graph_by_ref = {
        str(row.get("factor_ref") or ""): row
        for row in graph_rows
        if row.get("factor_ref")
    }
    output: list[Mapping[str, Any]] = []
    for reduced in reduced_factors:
        proposal_rows = tuple(
            proposal_by_ref[str(ref)]
            for ref in reduced.get("proposal_refs") or ()
            if str(ref) in proposal_by_ref
        )
        source_refs = {
            str((row.get("candidate_payload") or {}).get("source_factor_ref") or "")
            for row in proposal_rows
        } - {""}
        if len(source_refs) != 1:
            output.append(dict(reduced))
            continue
        source_ref = next(iter(source_refs))
        source = graph_by_ref.get(source_ref)
        if source is None:
            output.append(dict(reduced))
            continue
        metadata = dict(source.get("metadata") or {})
        provenance = {
            str(ref)
            for row in proposal_rows
            for ref in (
                *(row.get("source_span_refs") or ()),
                *(row.get("input_observation_refs") or ()),
                *(row.get("dependency_factor_refs") or ()),
                *(row.get("transport_refs") or ()),
                *(row.get("ontology_axis_refs") or ()),
            )
            if str(ref)
        }
        metadata.update(
            {
                "fibre_summary_ref": str(reduced.get("factor_ref") or ""),
                "semantic_coordinate_ref": str(
                    reduced.get("semantic_coordinate_ref") or ""
                ),
                "fibre_kind": str(reduced.get("fibre_kind") or "hypothesis"),
                "structural_signature_ref": str(
                    reduced.get("structural_signature") or ""
                ),
                "role_bindings": dict(reduced.get("role_bindings") or {}),
                "qualifier_state": dict(reduced.get("qualifier_state") or {}),
                "proposal_refs": sorted(
                    str(ref) for ref in reduced.get("proposal_refs") or ()
                ),
                "ontology_axis_refs": sorted(
                    str(ref) for ref in reduced.get("ontology_axis_refs") or ()
                ),
                "transport_refs": sorted(
                    str(ref) for ref in reduced.get("transport_refs") or ()
                ),
                "support_states": sorted(
                    str(ref) for ref in reduced.get("support_states") or ()
                ),
                "provenance_refs": sorted(
                    {*metadata.get("provenance_refs", ()), *provenance}
                ),
                "projection_factor_binding": "persisted_source_factor",
            }
        )
        output.append(
            {
                **source,
                "residuals": sorted(
                    {
                        *(str(ref) for ref in source.get("residuals") or ()),
                        *(str(ref) for ref in reduced.get("residuals") or ()),
                    }
                ),
                "metadata": metadata,
            }
        )
    return tuple(output)


__all__ = ["bind_projection_factor_rows"]
