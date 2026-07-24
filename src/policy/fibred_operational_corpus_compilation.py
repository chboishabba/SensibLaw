"""Fibred operational wrapper over the streaming document compiler.

The existing compiler still performs canonical parsing, mention licensing,
structural typing, local meets, and streaming job execution. This wrapper makes
the deterministic streamed fibre reduction the PNF materialised view returned
to persistence and downstream projections, evaluates the constraint frontier
against that view, and retains pre-fibre artifacts only as compatibility
evidence.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from src.pnf import PNFGraph, derive_resolution_demands
from src.pnf.constraint_worklist import evaluate_constraint_worklist
from src.pnf.fibred_build_projection import project_fibred_semantic_build
from src.pnf.streaming_reduction_projection import project_streaming_reduction
from src.policy import corpus_compilation as legacy
from src.policy.algebra import (
    Factor,
    FactorConstraint,
    TypedAlternative,
    canonicalize_factor_revision,
)
from src.policy.carriers.canonical import canonical_sha256
from src.policy.operational_corpus_compilation import (
    OPERATIONAL_COMPILER_CONTRACT,
    compile_document_operational,
)


FIBRED_OPERATIONAL_COMPILER_CONTRACT = (
    "postgres-fibred-semantic-compiler:v0_1"
)


def _alternative(row: Mapping[str, Any]) -> TypedAlternative[Any]:
    return TypedAlternative(
        alternative_ref=str(row["alternative_ref"]),
        value=row.get("value"),
        type_ref=str(row["type_ref"]),
        derivation_refs=tuple(row.get("derivation_refs") or ()),
        evidence_refs=tuple(row.get("evidence_refs") or ()),
        authority_state=str(row.get("authority_state") or "candidate_only"),
        metadata=dict(row.get("metadata") or {}),
    )


def _constraint(row: Mapping[str, Any]) -> FactorConstraint:
    return FactorConstraint(
        constraint_ref=str(row["constraint_ref"]),
        constraint_type=str(row["constraint_type"]),
        payload=dict(row.get("payload") or {}),
        provenance_refs=tuple(row.get("provenance_refs") or ()),
        source_factor_refs=tuple(row.get("source_factor_refs") or ()),
        target_factor_refs=tuple(row.get("target_factor_refs") or ()),
        alternative_group=(
            str(row["alternative_group"])
            if row.get("alternative_group") is not None
            else None
        ),
        required=bool(row.get("required", True)),
        residual_on_failure=(
            str(row["residual_on_failure"])
            if row.get("residual_on_failure")
            else None
        ),
    )


def _factor(row: Mapping[str, Any]) -> Factor[Any]:
    return Factor(
        factor_ref=str(row["factor_ref"]),
        factor_type=str(row["factor_type"]),
        alternatives=tuple(
            _alternative(value)
            for value in row.get("alternatives") or ()
            if isinstance(value, Mapping)
        ),
        constraints=tuple(
            _constraint(value)
            for value in row.get("constraints") or ()
            if isinstance(value, Mapping)
        ),
        residuals=tuple(row.get("residuals") or ()),
        closure_state=str(row.get("closure_state") or "open"),
        metadata=dict(row.get("metadata") or {}),
    )


def _graph(row: Mapping[str, Any]) -> PNFGraph:
    return PNFGraph(
        graph_ref=str(row["graph_ref"]),
        document_ref=str(row["document_ref"]),
        factors=tuple(
            _factor(value)
            for value in row.get("factors") or ()
            if isinstance(value, Mapping)
        ),
        constraints=tuple(
            _constraint(value)
            for value in row.get("constraints") or ()
            if isinstance(value, Mapping)
        ),
        relation_refs=tuple(row.get("relation_refs") or ()),
        residuals=tuple(row.get("residuals") or ()),
    )


def _reidentify_graph(graph: PNFGraph) -> PNFGraph:
    graph_ref = "pnf-fibred-graph:" + canonical_sha256(
        {
            "document_ref": graph.document_ref,
            "factors": [row.to_dict() for row in graph.factors],
            "constraints": [row.to_dict() for row in graph.constraints],
            "relation_refs": list(graph.relation_refs),
            "residuals": list(graph.residuals),
            "materialisation_contract": "deterministic-fibrewise-pnf:v0_1",
        }
    )
    return replace(graph, graph_ref=graph_ref)


def _canonicalize_factor_revisions(graph: PNFGraph) -> PNFGraph:
    """Refresh derived revision metadata after fibred materialisation."""

    return replace(
        graph,
        factors=tuple(
            _factor(canonicalize_factor_revision(factor.to_dict()))
            for factor in graph.factors
        ),
    )


def compile_document_fibred_operational(
    document_input: Mapping[str, Any],
    compiler_context: legacy.CompilerContext,
    *,
    closure_workers: int = 2,
    owner_partitions: int = 2,
) -> legacy.DocumentCompilation:
    """Compile a document and return the fibrewise PNF materialised view."""

    base = compile_document_operational(
        document_input,
        compiler_context,
        closure_workers=closure_workers,
        owner_partitions=owner_partitions,
    )
    artifacts = dict(base.artifacts)
    streaming_build = dict(artifacts.get("streaming_semantic_build") or {})
    source_graph_row = (
        artifacts.get("refined_pnf_graph")
        or artifacts.get("pnf_graph")
        or {}
    )
    source_graph = _graph(source_graph_row)
    fibred_graph, projection_receipt = project_streaming_reduction(
        graph=source_graph,
        streaming_build=streaming_build,
    )
    fibred_graph = _canonicalize_factor_revisions(_reidentify_graph(fibred_graph))
    changed_factor_refs = tuple(
        str(ref) for ref in projection_receipt.get("factor_refs") or ()
    )
    constraint_worklist = evaluate_constraint_worklist(
        document_ref=fibred_graph.document_ref,
        factor_refs=(row.factor_ref for row in fibred_graph.factors),
        constraints=fibred_graph.constraints,
        changed_factor_refs=(changed_factor_refs or None),
    )
    fibred_build = project_fibred_semantic_build(streaming_build)
    streaming_build.update(
        {
            "fibred_semantic_build": fibred_build,
            "fibre_ledger_ref": fibred_build["fibre_ledger"]["ledger_ref"],
            "integrated_producer_receipt": fibred_build[
                "integrated_producer_receipt"
            ],
            "fibre_boundary_obligations": fibred_build[
                "fibre_boundary_obligations"
            ],
            "materialized_pnf_graph_ref": fibred_graph.graph_ref,
            "materialized_view_authority": "deterministic_fibrewise_pnf",
            "constraint_worklist_ref": constraint_worklist.result_ref,
            "one_proposal_contract": True,
            "one_reduction_authority": True,
        }
    )
    compatibility_refinements = list(
        artifacts.get("factor_refinements") or ()
    )
    demands = derive_resolution_demands(fibred_graph)
    phase_boundary = dict(artifacts.get("phase_boundary") or {})
    phase_boundary.update(
        {
            "fibred_semantic_state": True,
            "constraints_after_fibre_materialisation": True,
            "one_integrated_producer": True,
            "one_proposal_contract": True,
            "one_reduction_authority": True,
        }
    )
    artifacts.update(
        {
            "pre_fibre_pnf_graph": artifacts.get("pnf_graph"),
            "pre_fibre_refined_pnf_graph": artifacts.get(
                "refined_pnf_graph"
            ),
            "pre_fibre_constraint_assessments": artifacts.get(
                "constraint_assessments"
            ),
            "compatibility_factor_refinements": compatibility_refinements,
            "factor_refinements": [],
            "constraint_assessments": [
                row.to_dict() for row in constraint_worklist.assessments
            ],
            "fibred_constraint_worklist": constraint_worklist.to_dict(),
            "pnf_graph": fibred_graph.to_dict(),
            "refined_pnf_graph": fibred_graph.to_dict(),
            # ``derive_resolution_demands`` deliberately returns canonical
            # mapping payloads.  Keep that backend-free contract intact at
            # the fibred boundary rather than treating demand rows as carrier
            # instances.
            "resolution_demands": [legacy.canonical_json(row) for row in demands],
            "streaming_semantic_build": streaming_build,
            "fibred_semantic_build": fibred_build,
            "streaming_reduction_projection": projection_receipt,
            "operational_compiler_contract": (
                FIBRED_OPERATIONAL_COMPILER_CONTRACT
            ),
            "base_operational_compiler_contract": OPERATIONAL_COMPILER_CONTRACT,
            "phase_boundary": phase_boundary,
        }
    )
    return legacy.DocumentCompilation(
        document_ref=base.document_ref,
        content_sha256=base.content_sha256,
        media_type=base.media_type,
        artifacts=artifacts,
        status=base.status,
        failure=base.failure,
    )


__all__ = [
    "FIBRED_OPERATIONAL_COMPILER_CONTRACT",
    "compile_document_fibred_operational",
]
