from src.pnf import FactorProposal, StreamingSemanticOwner
from src.runtime.stage_timing import StageTimingLedger


def _proposal(index: int) -> FactorProposal:
    return FactorProposal(
        document_ref="document:metrics",
        source_revision_ref="source:metrics",
        factor_type_ref="semantic.entity_link",
        source_span_refs=(f"span:{index}",),
        input_observation_refs=(),
        dependency_factor_refs=(),
        structural_signature="entity-link:v1",
        role_bindings={"mention": f"mention:{index}"},
        qualifier_state={},
        producer_contract="linker:test:v1",
        declaration_revision="v1",
        candidate_payload={"target_ref": f"wd:Q{index}"},
    )


def test_owner_retains_reduction_history_and_injects_base_timing_metrics() -> None:
    owner = StreamingSemanticOwner(document_ref="document:metrics")
    timing = StageTimingLedger(document_ref="document:metrics")

    with timing.stage("base_proposal_reduction") as stage:
        proposals = (_proposal(1), _proposal(2))
        owner.admit_proposals(proposals, stage="base")
        owner.reduce_dirty_groups()
        reduction = owner.materialized_reduction
        stage.record(
            input_edges=len(proposals),
            output_edges=len(reduction.factors),
        )

    payload = owner.to_dict()
    assert len(payload["reduction_history"]) == 1
    metrics = payload["reduction_history"][0]["metrics"]
    assert metrics["bucket_count"] == 2
    assert metrics["candidate_comparisons"] == 0
    assert reduction.metrics["bucket_count"] == 2
    assert timing.timings[0].details["fibre_partition_metrics"] == metrics


def test_reduction_history_does_not_change_graph_identity() -> None:
    owner = StreamingSemanticOwner(document_ref="document:metrics")
    proposal = _proposal(1)
    owner.admit_proposals((proposal,), stage="base")
    owner.reduce_dirty_groups()
    graph_ref = owner.materialized_reduction.graph_ref

    owner._reduction_history.append({"execution_only": "different"})
    assert owner.materialized_reduction.graph_ref == graph_ref
