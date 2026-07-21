"""Project a deterministic streamed proposal reduction into the PNF graph.

The projection is a compatibility materialisation only.  It consumes the converged
proposal ledger and reduced-factor revision, preserves all proposal alternatives and
residuals, and never re-runs parser/operator composition.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.language.operator_composition import OPERATOR_COMPOSITION_CONTRACT
from src.pnf.graph import PNFGraph
from src.policy.algebra import Factor, TypedAlternative
from src.policy.carriers.canonical import canonical_sha256


STREAMING_REDUCTION_PROJECTION_CONTRACT = (
    "streaming-reduction-pnf-projection:v0_1"
)


def _factor_from_reduction(
    *,
    reduced: Mapping[str, Any],
    proposals: Mapping[str, Mapping[str, Any]],
    reduction_ref: str,
) -> Factor[Any]:
    proposal_refs = tuple(
        sorted(str(ref) for ref in reduced.get("proposal_refs") or ())
    )
    proposal_rows = [proposals[ref] for ref in proposal_refs if ref in proposals]
    alternatives = tuple(
        TypedAlternative(
            alternative_ref=f"{str(reduced['factor_ref'])}:proposal:{index}",
            value={
                "predicate_ref": str(
                    (row.get("candidate_payload") or {}).get("predicate_ref")
                    or ""
                ),
                "role_bindings": dict(row.get("role_bindings") or {}),
                "qualifier_state": dict(row.get("qualifier_state") or {}),
                "candidate_payload": dict(row.get("candidate_payload") or {}),
                "proposal_ref": str(row["proposal_ref"]),
            },
            type_ref=f"{str(reduced['factor_type_ref'])}.candidate",
            derivation_refs=tuple(
                sorted(
                    {
                        str(row.get("producer_contract") or ""),
                        str(row.get("declaration_revision") or ""),
                        *(str(ref) for ref in row.get("source_span_refs") or ()),
                        *(
                            str(ref)
                            for ref in row.get("input_observation_refs") or ()
                        ),
                    }
                    - {""}
                )
            ),
        )
        for index, row in enumerate(proposal_rows)
    )
    residuals = tuple(sorted(str(value) for value in reduced.get("residuals") or ()))
    provenance_refs = tuple(
        sorted(
            {
                str(ref)
                for row in proposal_rows
                for ref in (
                    *(row.get("source_span_refs") or ()),
                    *(row.get("input_observation_refs") or ()),
                )
            }
        )
    )
    role_bindings = dict(reduced.get("role_bindings") or {})
    qualifier_state = dict(reduced.get("qualifier_state") or {})
    return Factor(
        factor_ref=str(reduced["factor_ref"]),
        factor_type=str(reduced["factor_type_ref"]),
        alternatives=alternatives,
        residuals=residuals,
        closure_state=(
            "requires_external_resolution" if residuals else "locally_closed"
        ),
        metadata={
            "factor_revision_ref": str(reduced["factor_revision_ref"]),
            "structural_signature_ref": str(
                reduced.get("structural_signature") or ""
            ),
            "role_bindings": role_bindings,
            "qualifier_state": qualifier_state,
            "proposal_refs": proposal_refs,
            "provenance_refs": provenance_refs,
            "streaming_reduction_ref": reduction_ref,
            "projection_contract_ref": STREAMING_REDUCTION_PROJECTION_CONTRACT,
            "authority": "candidate_pnf_only",
        },
    )


def project_streaming_reduction(
    *,
    graph: PNFGraph,
    streaming_build: Mapping[str, Any],
) -> tuple[PNFGraph, dict[str, Any]]:
    """Return a PNF graph containing streamed operator-composition factors."""

    materialized = streaming_build.get("materialized_reduction") or {}
    reduction_ref = str(materialized.get("graph_ref") or "")
    proposals = {
        str(row.get("proposal_ref") or ""): row
        for row in streaming_build.get("proposals") or ()
        if isinstance(row, Mapping) and row.get("proposal_ref")
    }
    operator_proposal_refs = {
        ref
        for ref, row in proposals.items()
        if str(row.get("producer_contract") or "")
        == OPERATOR_COMPOSITION_CONTRACT
    }
    selected = [
        row
        for row in materialized.get("factors") or ()
        if isinstance(row, Mapping)
        and operator_proposal_refs.intersection(
            str(ref) for ref in row.get("proposal_refs") or ()
        )
    ]
    result = graph
    factors = []
    for row in sorted(selected, key=lambda value: str(value["factor_ref"])):
        factor = _factor_from_reduction(
            reduced=row,
            proposals=proposals,
            reduction_ref=reduction_ref,
        )
        result = result.replace_factor(factor)
        factors.append(factor)
    receipt_identity = {
        "contract_ref": STREAMING_REDUCTION_PROJECTION_CONTRACT,
        "input_graph_ref": graph.graph_ref,
        "streaming_reduction_ref": reduction_ref,
        "factor_refs": [row.factor_ref for row in factors],
    }
    receipt = {
        **receipt_identity,
        "receipt_ref": "streaming-reduction-projection:"
        + canonical_sha256(receipt_identity),
        "output_graph_ref": result.graph_ref,
        "factor_count": len(factors),
        "parser_observation_source": "streaming_observation_ledger",
        "reparsed": False,
        "shared_graph_mutation": False,
        "identity_promoted": False,
        "legal_truth_closed": False,
        "authority": "compatibility_projection_only",
    }
    return result, receipt


__all__ = [
    "STREAMING_REDUCTION_PROJECTION_CONTRACT",
    "project_streaming_reduction",
]
