from __future__ import annotations

from dataclasses import replace

from src.pnf.factor_proposals import (
    INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
    FactorProposal,
    reduce_factor_proposals,
)
from src.pnf.integrated_semantic_producer import IntegratedSemanticProducer


def _proposal(
    *,
    role: str = "main",
    producer_scope: str = "integrated",
    execution_metadata: dict[str, object] | None = None,
) -> FactorProposal:
    return FactorProposal(
        document_ref="document:1",
        source_revision_ref="source-revision:1",
        factor_type_ref="semantic.entity_link",
        source_span_refs=("span:usa",),
        input_observation_refs=("observation:usa",),
        dependency_factor_refs=(),
        structural_signature="signature:entity-link:v1",
        role_bindings={"mention": "mention:usa", "target": "wd:Q30"},
        qualifier_state={"relation": "candidate_denotation"},
        producer_contract="linker:wikidata:v1",
        declaration_revision="v1",
        candidate_payload={"target_ref": "wd:Q30"},
        statement_role=role,
        fibre_kind="hypothesis",
        producer_scope=producer_scope,
        execution_metadata=execution_metadata or {},
    )


def test_ordinary_proposals_share_one_integrated_producer_contract() -> None:
    proposal = _proposal()

    assert proposal.producer_contract == INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
    assert proposal.operation_contract == "linker:wikidata:v1"
    assert proposal.producer_scope == "integrated"
    assert proposal.semantic_coordinate_ref.startswith("semantic-coordinate:")


def test_backend_telemetry_does_not_change_semantic_proposal_identity() -> None:
    python = _proposal(
        execution_metadata={"sub_executor_ref": "python-linker:v1"}
    )
    zelph = _proposal(
        execution_metadata={"sub_executor_ref": "zelph-linker:v1"}
    )

    assert python.proposal_ref == zelph.proposal_ref
    assert python.to_dict()["execution_metadata"] != zelph.to_dict()[
        "execution_metadata"
    ]


def test_external_enrichment_remains_distinct_from_integrated_core() -> None:
    proposal = _proposal(producer_scope="external")

    assert proposal.producer_contract == "linker:wikidata:v1"
    assert proposal.operation_contract == "linker:wikidata:v1"
    assert proposal.to_dict()["authority"] == "external_candidate"


def test_statement_roles_create_distinct_base_coordinates_and_fibres() -> None:
    main = _proposal(role="main")
    qualifier = _proposal(role="qualifier")
    reduction = reduce_factor_proposals(
        document_ref="document:1",
        proposals=(qualifier, main),
        known_observation_refs=("observation:usa",),
    )

    assert main.semantic_coordinate_ref != qualifier.semantic_coordinate_ref
    assert len(reduction.factors) == 2
    assert len(reduction.to_dict()["semantic_coordinate_refs"]) == 2
    assert reduction.to_dict()["fibrewise_reduction"] is True


def test_integrated_producer_builds_fibre_ledger_and_receipt() -> None:
    producer = IntegratedSemanticProducer()
    raw = _proposal()
    proposal = replace(
        raw,
        execution_metadata={"sub_executor_ref": "python-linker:v1"},
    )
    sub_receipt = producer.sub_executor_receipt(
        document_ref="document:1",
        operation_kind="linking",
        operation_contract=str(proposal.operation_contract),
        sub_executor_ref="python-linker:v1",
        declaration_ref="declaration:linking:v1",
        rule_set_revision="v1",
        input_refs=proposal.input_observation_refs,
        proposals=(proposal,),
    )
    ledger = producer.fibre_ledger(
        proposals=(proposal,),
        sub_executor_receipts=(sub_receipt,),
    )
    receipt = producer.receipt(
        document_ref="document:1",
        proposals=(proposal,),
        fibre_ledger=ledger,
        sub_executor_receipts=(sub_receipt,),
    )

    assert ledger.fibre(str(proposal.semantic_coordinate_ref))[0].content_ref == (
        proposal.proposal_ref
    )
    assert ledger.derivations[0].sub_executor_ref == "python-linker:v1"
    payload = receipt.to_dict()
    assert payload["one_proposal_contract"] is True
    assert payload["one_reduction_authority"] is True
    assert payload["identity_promoted"] is False
    assert payload["legal_truth_closed"] is False
