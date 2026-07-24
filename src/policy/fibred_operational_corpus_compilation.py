"""Fibred operational wrapper over the streaming document compiler.

The existing compiler performs canonical parsing, mention licensing, structural
typing, local meets, and streaming job execution. This wrapper makes fibrewise
reduction the PNF materialised view, then separately assesses, admits, resolves,
projects, and optionally executes it. Memory and learning remain outside the
SensibLaw compiler.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from src.pnf import PNFGraph, derive_resolution_demands
from src.pnf.constraint_worklist import evaluate_constraint_worklist
from src.pnf.domain_ir_projection import build_domain_ir
from src.pnf.fibred_build_projection import project_fibred_semantic_build
from src.pnf.ir_execution import execute_ir_requests
from src.pnf.lifecycle_assessment_projection import (
    annotate_assessment_proposals,
)
from src.pnf.projection_factor_binding import bind_projection_factor_rows
from src.pnf.semantic_lifecycle import build_semantic_lifecycle
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
    "postgres-fibred-semantic-compiler:v0_2"
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


def _demand_rows(
    graph: PNFGraph,
    projection_demands: tuple[Any, ...],
) -> tuple[dict[str, Any], ...]:
    rows = [
        legacy.canonical_json(row)
        for row in derive_resolution_demands(graph)
    ]
    rows.extend(row.to_resolution_demand() for row in projection_demands)
    by_ref = {
        str(row.get("demand_ref") or canonical_sha256(row)): row
        for row in rows
    }
    return tuple(by_ref[key] for key in sorted(by_ref))


def compile_document_fibred_operational(
    document_input: Mapping[str, Any],
    compiler_context: legacy.CompilerContext,
    *,
    closure_workers: int = 2,
    owner_partitions: int = 2,
) -> legacy.DocumentCompilation:
    """Compile one source through the explicit pre-memory semantic lifecycle."""

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
    fibred_graph = _canonicalize_factor_revisions(
        _reidentify_graph(fibred_graph)
    )
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

    proposal_rows = tuple(
        row
        for row in streaming_build.get("proposals") or ()
        if isinstance(row, Mapping)
    )
    lifecycle_proposal_rows = annotate_assessment_proposals(
        proposals=proposal_rows,
        work_items=constraint_worklist.work_items,
        coverage_notices=tuple(
            row
            for row in streaming_build.get("coverage_notices") or ()
            if isinstance(row, Mapping)
        ),
    )
    materialized_reduction = streaming_build.get("materialized_reduction") or {}
    reduced_factor_rows = tuple(
        row
        for row in materialized_reduction.get("factors") or ()
        if isinstance(row, Mapping)
    )
    reduction_residual_rows = tuple(
        row
        for row in materialized_reduction.get("residuals") or ()
        if isinstance(row, Mapping)
    )
    assessment_rows = tuple(
        row.to_dict() for row in constraint_worklist.assessments
    )
    lifecycle = build_semantic_lifecycle(
        document_ref=fibred_graph.document_ref,
        proposals=lifecycle_proposal_rows,
        reduced_factors=reduced_factor_rows,
        fibre_elements=tuple(fibred_build.get("fibre_elements") or ()),
        constraint_assessments=assessment_rows,
        reduction_residuals=reduction_residual_rows,
    )
    projection_factor_rows = bind_projection_factor_rows(
        reduced_factors=reduced_factor_rows,
        proposals=proposal_rows,
        graph_factors=fibred_graph.factors,
    )
    domain_ir = build_domain_ir(
        document_ref=fibred_graph.document_ref,
        resolutions=lifecycle.resolutions,
        factors=(
            *projection_factor_rows,
            *(row.to_dict() for row in fibred_graph.factors),
        ),
        proposals=proposal_rows,
    )
    execution_receipts = execute_ir_requests(
        requests=tuple(document_input.get("ir_execution_requests") or ()),
        domain_ir=domain_ir.projections,
    )
    demands = _demand_rows(fibred_graph, domain_ir.demands)

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
            "semantic_lifecycle_ref": lifecycle.lifecycle_ref,
            "domain_ir_build_ref": domain_ir.build_ref,
            "ir_execution_receipt_refs": [
                row.receipt_ref for row in execution_receipts
            ],
            "one_proposal_contract": True,
            "one_reduction_authority": True,
            "reduction_is_not_resolution": True,
            "memory_learning_deferred": True,
        }
    )
    compatibility_refinements = list(
        artifacts.get("factor_refinements") or ()
    )
    phase_boundary = dict(artifacts.get("phase_boundary") or {})
    phase_boundary.update(
        {
            "fibred_semantic_state": True,
            "constraints_after_fibre_materialisation": True,
            "candidate_assessment_separate": True,
            "admissibility_separate": True,
            "reduction_is_not_resolution": True,
            "domain_ir_is_lawful_projection": True,
            "projection_demands_return_to_pnf": True,
            "execution_requires_applicability_witness": True,
            "memory_learning_deferred": True,
            "one_integrated_producer": True,
            "one_proposal_contract": True,
            "one_reduction_authority": True,
        }
    )
    lifecycle_row = lifecycle.to_dict()
    domain_ir_row = domain_ir.to_dict()
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
            "constraint_assessments": assessment_rows,
            "fibred_constraint_worklist": constraint_worklist.to_dict(),
            "pnf_graph": fibred_graph.to_dict(),
            "refined_pnf_graph": fibred_graph.to_dict(),
            "semantic_lifecycle": lifecycle_row,
            "candidate_assessments": lifecycle_row[
                "candidate_assessments"
            ],
            "admissibility_receipts": lifecycle_row[
                "admissibility_receipts"
            ],
            "semantic_resolution_receipts": lifecycle_row[
                "resolution_receipts"
            ],
            "domain_ir_build": domain_ir_row,
            "domain_ir_projections": domain_ir_row["projections"],
            "domain_ir_projection_receipts": domain_ir_row["receipts"],
            "projection_loss_receipts": domain_ir_row["losses"],
            "projection_demands": domain_ir_row["demands"],
            "ir_execution_receipts": [
                row.to_dict() for row in execution_receipts
            ],
            "resolution_demands": list(demands),
            "streaming_semantic_build": streaming_build,
            "fibred_semantic_build": fibred_build,
            "streaming_reduction_projection": projection_receipt,
            "operational_compiler_contract": (
                FIBRED_OPERATIONAL_COMPILER_CONTRACT
            ),
            "base_operational_compiler_contract": (
                OPERATIONAL_COMPILER_CONTRACT
            ),
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
