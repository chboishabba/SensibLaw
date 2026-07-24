from __future__ import annotations

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals
from src.policy import fibred_operational_corpus_compilation as module
from src.policy.algebra import factor_revision_ref
from src.policy.corpus_compilation import DocumentCompilation, default_compiler_context


def _factor() -> dict[str, object]:
    return {
        "factor_ref": "factor:source",
        "factor_type": "semantic.normative_relation",
        "alternatives": [],
        "constraints": [],
        "residuals": [],
        "closure_state": "open",
        "metadata": {},
    }


def _base_compilation(
    proposal: FactorProposal,
) -> tuple[DocumentCompilation, object]:
    reduction = reduce_factor_proposals(
        document_ref="document:1",
        proposals=(proposal,),
    )
    graph = {
        "schema_version": "sl.pnf_graph.v0_1",
        "graph_ref": "pnf-graph:before",
        "document_ref": "document:1",
        "factors": [_factor()],
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
            "factor_refinements": [{"refinement_ref": "legacy:1"}],
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
    return base, reduction


def _compile(monkeypatch, base: DocumentCompilation) -> DocumentCompilation:
    monkeypatch.setattr(
        module,
        "compile_document_operational",
        lambda *args, **kwargs: base,
    )
    return module.compile_document_fibred_operational(
        {
            "document_ref": "document:1",
            "content_sha256": "content:1",
            "media_type": "text/plain",
            "canonical_text": "Driver must drive.",
            "source_ref": "source:1",
        },
        default_compiler_context(),
    )


def test_fibred_wrapper_replaces_existing_compatibility_coordinate(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module,
        "derive_resolution_demands",
        lambda graph: ({"demand_ref": "demand:1", "graph_ref": graph.graph_ref},),
    )
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.normative_relation",
        source_span_refs=("span:1",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="normative:v1",
        role_bindings={"conduct": "eventuality:drive"},
        qualifier_state={"modality": "obligation"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v1",
        candidate_payload={
            "source_factor_ref": "factor:source",
            "predicate_ref": "normative.obligation",
        },
        scope_ref="sentence:1",
        fibre_kind="composition",
    )
    base, reduction = _base_compilation(proposal)
    compilation = _compile(monkeypatch, base)
    artifacts = compilation.artifacts
    factor = artifacts["pnf_graph"]["factors"][0]
    receipt = artifacts["streaming_reduction_projection"]

    assert artifacts["pnf_graph"]["graph_ref"].startswith(
        "pnf-fibred-graph:"
    )
    assert factor["factor_ref"] == "factor:source"
    assert factor["metadata"]["fibre_summary_ref"] == (
        reduction.factors[0].factor_ref
    )
    assert factor_revision_ref(factor) == factor["metadata"]["factor_revision_ref"]
    assert receipt["replaced_factor_count"] == 1
    assert receipt["added_factor_count"] == 0
    assert artifacts["factor_refinements"] == []
    assert artifacts["compatibility_factor_refinements"] == [
        {"refinement_ref": "legacy:1"}
    ]
    assert artifacts["fibred_semantic_build"]["one_proposal_contract"] is True
    assert artifacts["streaming_semantic_build"]["one_reduction_authority"] is True
    assert artifacts["phase_boundary"]["fibred_semantic_state"] is True
    assert artifacts["phase_boundary"][
        "constraints_after_fibre_materialisation"
    ] is True
    assert artifacts["resolution_demands"]
    assert all(isinstance(row, dict) for row in artifacts["resolution_demands"])


def test_fibred_wrapper_adds_new_higher_order_coordinate(monkeypatch) -> None:
    proposal = FactorProposal(
        document_ref="document:1",
        source_revision_ref="source:1",
        factor_type_ref="semantic.legal_exception",
        source_span_refs=("span:unless",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="exception:v1",
        role_bindings={"host": "factor:source"},
        qualifier_state={"marker": "unless"},
        producer_contract="grammar:semantic:operator-composition:v0_1",
        declaration_revision="v1",
        candidate_payload={"predicate_ref": "legal.exception"},
        scope_ref="sentence:1",
        fibre_kind="composition",
    )
    base, reduction = _base_compilation(proposal)
    compilation = _compile(monkeypatch, base)
    artifacts = compilation.artifacts
    factors = artifacts["pnf_graph"]["factors"]
    receipt = artifacts["streaming_reduction_projection"]

    assert len(factors) == 2
    added = next(
        row for row in factors if row["factor_ref"] == reduction.factors[0].factor_ref
    )
    assert added["metadata"]["fibre_summary_ref"] == added["factor_ref"]
    assert receipt["added_factor_count"] == 1
    assert receipt["replaced_factor_count"] == 0
