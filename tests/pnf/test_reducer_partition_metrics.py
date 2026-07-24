from dataclasses import replace

from src.pnf.factor_proposals import FactorProposal, reduce_factor_proposals


def _proposal(index: int, *, scope: str) -> FactorProposal:
    return FactorProposal(
        document_ref="document:partition-test",
        source_revision_ref="source:1",
        factor_type_ref="semantic.entity_link",
        source_span_refs=(scope,),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="entity-link:v1",
        role_bindings={"mention": f"mention:{index}"},
        qualifier_state={},
        producer_contract="linker:test:v1",
        declaration_revision="v1",
        candidate_payload={"target_ref": f"wd:Q{index}"},
        scope_ref=scope,
    )


def test_partitioning_avoids_cross_fibre_comparisons_without_identity_drift() -> None:
    proposals = tuple(_proposal(index, scope=f"span:{index}") for index in range(6))
    forward = reduce_factor_proposals(
        document_ref="document:partition-test",
        proposals=proposals,
    )
    reverse = reduce_factor_proposals(
        document_ref="document:partition-test",
        proposals=tuple(reversed(proposals)),
    )

    assert forward.graph_ref == reverse.graph_ref
    assert forward.metrics["bucket_count"] == 6
    assert forward.metrics["largest_bucket"] == 1
    assert forward.metrics["candidate_comparisons"] == 0
    assert forward.metrics["comparison_avoidance_ratio"] == 1.0


def test_execution_metrics_do_not_enter_graph_identity() -> None:
    first = _proposal(1, scope="span:1")
    second = replace(first, execution_metadata={"backend": "zelph"})
    left = reduce_factor_proposals(
        document_ref=first.document_ref,
        proposals=(first,),
    )
    right = reduce_factor_proposals(
        document_ref=second.document_ref,
        proposals=(second,),
    )

    assert first.proposal_ref == second.proposal_ref
    assert left.graph_ref == right.graph_ref
    assert left.to_dict()["metrics"] == right.to_dict()["metrics"]
