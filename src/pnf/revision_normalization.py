"""Normalize legacy factor revisions onto canonical content identity."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.policy.algebra.revision_identity import (
    canonicalize_factor_revision,
    computed_factor_revision_ref,
    strip_factor_revision_ref,
)
from src.policy.carriers.canonical import canonical_sha256


def _graph_ref(graph: Mapping[str, Any], factors: Sequence[Mapping[str, Any]]) -> str:
    return "pnf-graph:" + canonical_sha256(
        {
            "document_ref": graph.get("document_ref"),
            "factors": list(factors),
            "constraints": graph.get("constraints") or (),
            "relation_refs": graph.get("relation_refs") or (),
            "revision_identity_contract": "content-addressed-factor:v0_1",
        }
    )


def _normalise_base_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    factors = [
        strip_factor_revision_ref(row) for row in graph.get("factors") or ()
    ]
    factors.sort(key=lambda row: str(row.get("factor_ref") or ""))
    result = dict(graph)
    result["factors"] = factors
    result["graph_ref"] = _graph_ref(result, factors)
    return result


def _normalise_refinements(
    refinements: Sequence[Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    rows: list[dict[str, Any]] = []
    resulting_by_factor: dict[str, dict[str, Any]] = {}
    refinement_ref_map: dict[str, str] = {}
    for source in refinements:
        row = dict(source)
        prior = strip_factor_revision_ref(row.get("prior_factor") or {})
        resulting = canonicalize_factor_revision(
            row.get("resulting_factor") or {}
        )
        factor_ref = str(
            prior.get("factor_ref") or resulting.get("factor_ref") or ""
        )
        if not factor_ref:
            continue
        prior_revision_ref = computed_factor_revision_ref(prior)
        resulting_revision_ref = computed_factor_revision_ref(resulting)
        delta = dict(row.get("refinement_delta") or {})
        delta.update(
            {
                "prior_factor_revision_ref": prior_revision_ref,
                "resulting_factor_revision_ref": resulting_revision_ref,
            }
        )
        identity = {
            "factor_ref": factor_ref,
            "prior_factor_revision_ref": prior_revision_ref,
            "resulting_factor_revision_ref": resulting_revision_ref,
            "added_alternative_refs": sorted(
                str(ref) for ref in row.get("added_alternative_refs") or ()
            ),
            "retained_alternative_refs": sorted(
                str(ref) for ref in row.get("retained_alternative_refs") or ()
            ),
            "rejected_alternative_refs": sorted(
                str(ref) for ref in row.get("rejected_alternative_refs") or ()
            ),
            "residual_transitions": list(row.get("residual_transitions") or ()),
            "candidate_set_refs": sorted(
                str(ref) for ref in row.get("candidate_set_refs") or ()
            ),
        }
        old_ref = str(row.get("refinement_ref") or "")
        new_ref = "factor-refinement:" + canonical_sha256(identity)
        if old_ref:
            refinement_ref_map[old_ref] = new_ref
        row.update(
            {
                "refinement_ref": new_ref,
                "prior_factor": prior,
                "resulting_factor": resulting,
                "refinement_delta": delta,
                "revision_identity_contract": "content-addressed-factor:v0_1",
            }
        )
        rows.append(row)
        resulting_by_factor[factor_ref] = resulting
    rows.sort(key=lambda row: str(row.get("refinement_ref") or ""))
    return rows, resulting_by_factor, refinement_ref_map


def _normalise_refined_graph(
    graph: Mapping[str, Any],
    *,
    resulting_by_factor: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []
    for source in graph.get("factors") or ():
        factor_ref = str(source.get("factor_ref") or "")
        replacement = resulting_by_factor.get(factor_ref)
        if replacement is not None:
            factors.append(dict(replacement))
        else:
            factors.append(strip_factor_revision_ref(source))
    factors.sort(key=lambda row: str(row.get("factor_ref") or ""))
    result = dict(graph)
    result["factors"] = factors
    result["graph_ref"] = _graph_ref(result, factors)
    return result


def _factor_revision_map(
    base_graph: Mapping[str, Any],
    refined_graph: Mapping[str, Any],
) -> dict[str, str]:
    revisions = {
        str(row["factor_ref"]): computed_factor_revision_ref(row)
        for row in base_graph.get("factors") or ()
    }
    revisions.update(
        {
            str(row["factor_ref"]): computed_factor_revision_ref(row)
            for row in refined_graph.get("factors") or ()
        }
    )
    return revisions


def _normalise_demands(
    demands: Sequence[Mapping[str, Any]],
    *,
    factor_revisions: Mapping[str, str],
    graph_ref: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in demands:
        row = dict(source)
        factor_ref = str(row.get("factor_ref") or "")
        revision_ref = factor_revisions.get(factor_ref)
        if revision_ref:
            row["factor_revision_ref"] = revision_ref
        row["graph_ref"] = graph_ref
        semantic_key = dict(row.get("semantic_key") or {})
        if revision_ref:
            semantic_key["factor_revision_ref"] = revision_ref
        semantic_key["graph_ref"] = graph_ref
        row["semantic_key"] = semantic_key
        row["demand_ref"] = "demand:" + canonical_sha256(semantic_key)
        rows.append(row)
    rows.sort(key=lambda row: str(row.get("demand_ref") or ""))
    return rows


def normalize_factor_revision_artifacts(
    artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    """Rewrite legacy revision metadata and dependent refs canonically.

    This is an explicit compiler migration step. It does not change factor
    alternatives, residual semantics, evidence assessments, or authority.
    """

    result = dict(artifacts)
    base_graph = _normalise_base_graph(artifacts.get("pnf_graph") or {})
    refinements, resulting_by_factor, refinement_ref_map = _normalise_refinements(
        artifacts.get("factor_refinements") or ()
    )
    refined_graph = _normalise_refined_graph(
        artifacts.get("refined_pnf_graph") or base_graph,
        resulting_by_factor=resulting_by_factor,
    )
    factor_revisions = _factor_revision_map(base_graph, refined_graph)
    meets: list[dict[str, Any]] = []
    for source in artifacts.get("typed_meets") or ():
        row = dict(source)
        refinement_ref = str(row.get("refinement_ref") or "")
        if refinement_ref in refinement_ref_map:
            row["refinement_ref"] = refinement_ref_map[refinement_ref]
        meets.append(row)
    result["pnf_graph"] = base_graph
    result["refined_pnf_graph"] = refined_graph
    result["factor_refinements"] = refinements
    result["typed_meets"] = sorted(
        meets, key=lambda row: str(row.get("meet_ref") or "")
    )
    result["resolution_demands"] = _normalise_demands(
        artifacts.get("resolution_demands") or (),
        factor_revisions=factor_revisions,
        graph_ref=str(refined_graph.get("graph_ref") or ""),
    )
    result["factor_revision_normalization"] = {
        "identity_contract": "content-addressed-factor:v0_1",
        "normalized_refinement_count": len(refinements),
        "rewritten_refinement_refs": len(refinement_ref_map),
        "authority": "identity_normalization_only",
    }
    return result


__all__ = ["normalize_factor_revision_artifacts"]
