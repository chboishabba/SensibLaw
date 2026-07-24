"""Project deterministic fibrewise proposal reduction into the PNF graph.

The projection consumes the converged proposal ledger and reduced fibre
summaries, preserves every proposal alternative and residual, and never re-runs
parser or operator composition. It is a materialised view, not a second
semantic authority. Reduced fibre-summary identity remains explicit while a
source compatibility factor reference is retained when one exists. A genuinely
new composed coordinate is added deterministically rather than forced through a
replacement-only API.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.language.operator_composition import OPERATOR_COMPOSITION_CONTRACT
from src.pnf.factor_proposals import INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
from src.pnf.graph import PNFGraph
from src.policy.algebra import Factor, TypedAlternative
from src.policy.carriers.canonical import canonical_sha256


STREAMING_REDUCTION_PROJECTION_CONTRACT = (
    "streaming-reduction-pnf-projection:v0_2"
)


def _materialized_factor_ref(
    reduced: Mapping[str, Any],
    proposal_rows: list[Mapping[str, Any]],
) -> str:
    source_refs = {
        str((row.get("candidate_payload") or {}).get("source_factor_ref") or "")
        for row in proposal_rows
    } - {""}
    if len(source_refs) == 1:
        return next(iter(source_refs))
    return str(reduced["factor_ref"])


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
    factor_ref = _materialized_factor_ref(reduced, proposal_rows)
    alternatives = tuple(
        TypedAlternative(
            alternative_ref=f"{factor_ref}:proposal:{index}",
            value={
                "predicate_ref": str(
                    (row.get("candidate_payload") or {}).get("predicate_ref")
                    or ""
                ),
                "semantic_coordinate_ref": str(
                    row.get("semantic_coordinate_ref") or ""
                ),
                "fibre_kind": str(row.get("fibre_kind") or "hypothesis"),
                "derivation_role": str(
                    row.get("derivation_role") or "support"
                ),
                "support_state": str(row.get("support_state") or "candidate"),
                "confidence": row.get("confidence"),
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
                        str(row.get("operation_contract") or ""),
                        str(row.get("declaration_revision") or ""),
                        *(str(ref) for ref in row.get("source_span_refs") or ()),
                        *(
                            str(ref)
                            for ref in row.get("input_observation_refs") or ()
                        ),
                        *(str(ref) for ref in row.get("transport_refs") or ()),
                        *(
                            str(ref)
                            for ref in row.get("ontology_axis_refs") or ()
                        ),
                    }
                    - {""}
                )
            ),
        )
        for index, row in enumerate(proposal_rows)
    )
    residuals = tuple(
        sorted(str(value) for value in reduced.get("residuals") or ())
    )
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
    fibre_summary_ref = str(reduced["factor_ref"])
    factor_revision_ref = str(
        reduced.get("factor_revision_ref")
        or "factor-revision:"
        + canonical_sha256(
            {
                "factor_ref": factor_ref,
                "fibre_summary_ref": fibre_summary_ref,
                "proposal_refs": proposal_refs,
                "residuals": residuals,
            }
        )
    )
    return Factor(
        factor_ref=factor_ref,
        factor_type=str(reduced["factor_type_ref"]),
        alternatives=alternatives,
        residuals=residuals,
        closure_state=(
            "requires_external_resolution" if residuals else "locally_closed"
        ),
        metadata={
            "factor_revision_ref": factor_revision_ref,
            "fibre_summary_ref": fibre_summary_ref,
            "semantic_coordinate_ref": str(
                reduced.get("semantic_coordinate_ref") or ""
            ),
            "fibre_kind": str(reduced.get("fibre_kind") or "hypothesis"),
            "structural_signature_ref": str(
                reduced.get("structural_signature") or ""
            ),
            "role_bindings": role_bindings,
            "qualifier_state": qualifier_state,
            "proposal_refs": proposal_refs,
            "derivation_roles": list(
                reduced.get("derivation_roles") or ()
            ),
            "ontology_axis_refs": list(
                reduced.get("ontology_axis_refs") or ()
            ),
            "transport_refs": list(reduced.get("transport_refs") or ()),
            "support_states": list(reduced.get("support_states") or ()),
            "provenance_refs": provenance_refs,
            "streaming_reduction_ref": reduction_ref,
            "projection_contract_ref": STREAMING_REDUCTION_PROJECTION_CONTRACT,
            "integrated_producer_contract": (
                INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
            ),
            "authority": "candidate_pnf_only",
        },
    )


def _is_operator_proposal(row: Mapping[str, Any]) -> bool:
    operation_contract = str(row.get("operation_contract") or "")
    producer_contract = str(row.get("producer_contract") or "")
    return operation_contract == OPERATOR_COMPOSITION_CONTRACT or (
        not operation_contract
        and producer_contract == OPERATOR_COMPOSITION_CONTRACT
    )


def _admit_factor(graph: PNFGraph, factor: Factor[Any]) -> tuple[PNFGraph, str]:
    known_refs = {row.factor_ref for row in graph.factors}
    if factor.factor_ref in known_refs:
        return graph.replace_factor(factor), "replaced"
    return (
        PNFGraph(
            graph_ref=graph.graph_ref,
            document_ref=graph.document_ref,
            factors=tuple(
                sorted((*graph.factors, factor), key=lambda row: row.factor_ref)
            ),
            constraints=graph.constraints,
            relation_refs=graph.relation_refs,
            residuals=graph.residuals,
        ),
        "added",
    )


def project_streaming_reduction(
    *,
    graph: PNFGraph,
    streaming_build: Mapping[str, Any],
) -> tuple[PNFGraph, dict[str, Any]]:
    """Return the PNF graph materialised from streamed composition fibres."""

    materialized = streaming_build.get("materialized_reduction") or {}
    reduction_ref = str(materialized.get("graph_ref") or "")
    proposals = {
        str(row.get("proposal_ref") or ""): row
        for row in streaming_build.get("proposals") or ()
        if isinstance(row, Mapping) and row.get("proposal_ref")
    }
    operator_proposal_refs = {
        ref for ref, row in proposals.items() if _is_operator_proposal(row)
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
    admissions: list[dict[str, str]] = []
    for row in sorted(selected, key=lambda value: str(value["factor_ref"])):
        factor = _factor_from_reduction(
            reduced=row,
            proposals=proposals,
            reduction_ref=reduction_ref,
        )
        result, admission = _admit_factor(result, factor)
        factors.append(factor)
        admissions.append(
            {"factor_ref": factor.factor_ref, "admission": admission}
        )
    receipt_identity = {
        "contract_ref": STREAMING_REDUCTION_PROJECTION_CONTRACT,
        "input_graph_ref": graph.graph_ref,
        "streaming_reduction_ref": reduction_ref,
        "factor_refs": [row.factor_ref for row in factors],
        "admissions": admissions,
        "fibre_summary_refs": sorted(
            {
                str(row.metadata.get("fibre_summary_ref") or "")
                for row in factors
            }
            - {""}
        ),
        "semantic_coordinate_refs": sorted(
            {
                str(row.metadata.get("semantic_coordinate_ref") or "")
                for row in factors
            }
            - {""}
        ),
    }
    receipt = {
        **receipt_identity,
        "receipt_ref": "streaming-reduction-projection:"
        + canonical_sha256(receipt_identity),
        "output_graph_ref": result.graph_ref,
        "factor_count": len(factors),
        "added_factor_count": sum(
            row["admission"] == "added" for row in admissions
        ),
        "replaced_factor_count": sum(
            row["admission"] == "replaced" for row in admissions
        ),
        "parser_observation_source": "streaming_observation_ledger",
        "reparsed": False,
        "fibrewise_materialisation": True,
        "compatibility_factor_refs_preserved": True,
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
