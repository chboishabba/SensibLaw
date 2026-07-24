from src.pnf.legal_ir_parity import (
    CuratedLegalIRParityReceipt,
    SemanticIdentitySnapshot,
    compare_identity_snapshots,
)


def test_identity_parity_ignores_execution_telemetry_by_construction() -> None:
    control = SemanticIdentitySnapshot(
        proposal_refs=("proposal:1",),
        factor_refs=("factor:1",),
        graph_refs=("graph:1",),
        fibre_ledger_refs=("ledger:1",),
    )
    candidate = SemanticIdentitySnapshot(
        factor_refs=("factor:1",),
        proposal_refs=("proposal:1",),
        fibre_ledger_refs=("ledger:1",),
        graph_refs=("graph:1",),
    )

    parity = compare_identity_snapshots(control, candidate)
    assert parity.identical is True
    assert parity.added_refs == {}
    assert parity.removed_refs == {}


def test_parity_receipt_never_promotes_legal_truth() -> None:
    snapshot = SemanticIdentitySnapshot(graph_refs=("graph:1",))
    receipt = CuratedLegalIRParityReceipt(
        corpus_ref="corpus:1",
        admission_profile_ref="profile:offline-hca-regression:v0_2",
        compiler_contract_ref="postgres-fibred-semantic-compiler:v0_1",
        source_revision_refs=("source:1",),
        ordinary_graph_refs=("graph:1",),
        legal_graph_refs=(),
        demand_refs=("demand:1",),
        plan_refs=("plan:1",),
        legal_ir_refs=(),
        typed_meet_refs=(),
        legacy_witness_refs=(),
        identity_snapshot=snapshot.to_dict(),
        control_snapshot=None,
        identity_parity=None,
        network_attempt_count=0,
    )
    payload = receipt.to_dict()
    assert payload["semantic_state_promoted"] is False
    assert payload["applicability_closed"] is False
    assert payload["legal_truth_closed"] is False
