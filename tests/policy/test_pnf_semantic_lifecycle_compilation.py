from __future__ import annotations

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.policy import fibred_operational_corpus_compilation as module
from src.policy.corpus_compilation import DocumentCompilation, default_compiler_context


def test_fibred_compiler_separates_reduction_resolution_and_legal_projection(
    monkeypatch,
) -> None:
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=("span:1",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="signature:normative:v1",
        role_bindings={"bearer": "entity:driver", "conduct": "event:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v1",
        candidate_payload={
            "source_factor_ref": "factor:source",
            "predicate_ref": "normative.obligation",
        },
        residuals=("jurisdiction_unresolved",),
        scope_ref="sentence:1",
        fibre_kind="composition",
        support_state="supported_with_residuals",
    )
    reduction = reduce_factor_proposals(
        document_ref="document:1",
        proposals=(proposal,),
    )
    graph = {
        "schema_version": "sl.pnf_graph.v0_1",
        "graph_ref": "pnf-graph:before",
        "document_ref": "document:1",
        "factors": [
            {
                "factor_ref": "factor:source",
                "factor_type": "semantic.normative_relation",
                "alternatives": [],
                "constraints": [],
                "residuals": ["jurisdiction_unresolved"],
                "closure_state": "requires_external_resolution",
                "metadata": {},
            }
        ],
        "constraints": [],
        "relation_refs": [],
        "residuals": [],
        "authority": "candidate_only",
    }
    base = DocumentCompilation(
        document_ref="document:1",
        content_sha256="content:1",
        media_type="text/plain",
        artifacts={
            "pnf_graph": graph,
            "refined_pnf_graph": graph,
            "factor_refinements": [],
            "streaming_semantic_build": {
                "document_ref": "document:1",
                "observation_deltas": [],
                "proposals": [proposal.to_dict()],
                "solver_jobs": [],
                "solver_receipts": [],
                "materialized_reduction": reduction.to_dict(),
            },
            "phase_boundary": {},
        },
    )
    monkeypatch.setattr(
        module,
        "compile_document_operational",
        lambda *args, **kwargs: base,
    )

    compilation = module.compile_document_fibred_operational(
        {
            "document_ref": "document:1",
            "content_sha256": "content:1",
            "media_type": "text/plain",
            "canonical_text": "Driver must drive.",
            "source_ref": "source:1",
        },
        default_compiler_context(),
    )
    artifacts = compilation.artifacts

    assert artifacts["semantic_lifecycle"]["reduction_is_not_resolution"] is True
    assert artifacts["semantic_resolution_receipts"][0]["state"] == (
        "resolved_unique"
    )
    assert any(
        row["domain"] == "retrieval"
        for row in artifacts["domain_ir_projections"]
    )
    assert any(
        row["demand_kind"] == "missing_jurisdiction"
        for row in artifacts["projection_demands"]
    )
    assert artifacts["phase_boundary"]["projection_demands_return_to_pnf"] is True
    assert artifacts["phase_boundary"]["memory_learning_deferred"] is True
    assert artifacts["ir_execution_receipts"] == []
