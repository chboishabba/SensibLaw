"""One integrated semantic producer over the fibred PNF proposal contract.

spaCy adapters, deterministic Python operations, Zelph closure, ontology
lookups, and selected learned scorers may be internal executors.  They do not
publish parallel semantic graphs.  Ordinary results are normalised under one
producer family, retain their operation contract and executor receipt, and
enter the same fibrewise deterministic reducer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from src.pnf.factor_proposals import (
    INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
    FactorProposal,
)
from src.pnf.semantic_fibres import (
    AxisObligation,
    FibreBoundaryObligation,
    FibreDerivation,
    OntologyAxis,
    SemanticCoordinate,
    SemanticFibreLedger,
    SemanticTransport,
    fibre_element_from_proposal_row,
)
from src.policy.carriers.canonical import canonical_sha256


INTEGRATED_PRODUCER_RECEIPT_SCHEMA_VERSION = (
    "sl.pnf.integrated_producer_receipt.v0_1"
)
SUB_EXECUTOR_RECEIPT_SCHEMA_VERSION = "sl.pnf.sub_executor_receipt.v0_1"
INTEGRATED_PRODUCER_CONTRACT_SCHEMA_VERSION = (
    "sl.pnf.integrated_producer_contract.v0_1"
)

_OPERATION_KINDS = {
    "observation",
    "typing",
    "linking",
    "attachment",
    "composition",
    "constraint",
    "closure",
    "enrichment",
    "residual",
}

_OPERATION_TO_FIBRE = {
    "observation": "observation",
    "typing": "hypothesis",
    "linking": "hypothesis",
    "attachment": "hypothesis",
    "composition": "composition",
    "constraint": "constraint",
    "closure": "consequence",
    "enrichment": "enrichment",
    "residual": "residual",
}


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class ProducerCapability:
    operation_kind: str
    operation_contract: str
    executor_refs: tuple[str, ...]
    declaration_refs: tuple[str, ...] = ()
    ontology_axis_refs: tuple[str, ...] = ()
    core: bool = True

    def __post_init__(self) -> None:
        if self.operation_kind not in _OPERATION_KINDS:
            raise ValueError("unsupported integrated producer operation")

    @property
    def capability_ref(self) -> str:
        return "integrated-producer-capability:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "operation_kind": self.operation_kind,
            "operation_contract": self.operation_contract,
            "executor_refs": list(_refs(self.executor_refs)),
            "declaration_refs": list(_refs(self.declaration_refs)),
            "ontology_axis_refs": list(_refs(self.ontology_axis_refs)),
            "core": self.core,
        }
        if include_ref:
            payload["capability_ref"] = self.capability_ref
        return payload


@dataclass(frozen=True)
class IntegratedProducerContract:
    contract_ref: str = INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
    contract_revision: str = "v0_1"
    proposal_schema_ref: str = "sl.pnf.factor_proposal.v0_2"
    reduction_contract_ref: str = "deterministic-fibrewise-pnf:v0_1"
    capabilities: tuple[ProducerCapability, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INTEGRATED_PRODUCER_CONTRACT_SCHEMA_VERSION,
            "contract_ref": self.contract_ref,
            "contract_revision": self.contract_revision,
            "proposal_schema_ref": self.proposal_schema_ref,
            "reduction_contract_ref": self.reduction_contract_ref,
            "capabilities": [
                row.to_dict()
                for row in sorted(
                    self.capabilities,
                    key=lambda value: value.capability_ref,
                )
            ],
            "one_proposal_contract": True,
            "one_reduction_authority": True,
            "parallel_authoritative_graphs": False,
        }


@dataclass(frozen=True)
class SubExecutorReceipt:
    document_ref: str
    operation_kind: str
    operation_contract: str
    sub_executor_ref: str
    declaration_ref: str
    rule_set_revision: str
    input_refs: tuple[str, ...]
    proposal_refs: tuple[str, ...]
    residual_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.operation_kind not in _OPERATION_KINDS:
            raise ValueError("unsupported sub-executor operation")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "operation_kind": self.operation_kind,
            "operation_contract": self.operation_contract,
            "sub_executor_ref": self.sub_executor_ref,
            "declaration_ref": self.declaration_ref,
            "rule_set_revision": self.rule_set_revision,
            "input_refs": list(_refs(self.input_refs)),
            "proposal_refs": list(_refs(self.proposal_refs)),
            "residual_refs": list(_refs(self.residual_refs)),
            "assumptions": list(_refs(self.assumptions)),
        }

    @property
    def receipt_ref(self) -> str:
        return "semantic-sub-executor-receipt:" + canonical_sha256(
            self.identity_payload()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SUB_EXECUTOR_RECEIPT_SCHEMA_VERSION,
            "receipt_ref": self.receipt_ref,
            **self.identity_payload(),
            "metrics": dict(self.metrics),
            "semantic_state_promoted": False,
        }


@dataclass(frozen=True)
class IntegratedProducerReceipt:
    document_ref: str
    contract_ref: str
    proposal_refs: tuple[str, ...]
    sub_executor_receipt_refs: tuple[str, ...]
    fibre_ledger_ref: str
    residual_refs: tuple[str, ...] = ()
    external_proposal_refs: tuple[str, ...] = ()

    @property
    def receipt_ref(self) -> str:
        return "integrated-semantic-producer-receipt:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": INTEGRATED_PRODUCER_RECEIPT_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "contract_ref": self.contract_ref,
            "proposal_refs": list(_refs(self.proposal_refs)),
            "sub_executor_receipt_refs": list(
                _refs(self.sub_executor_receipt_refs)
            ),
            "fibre_ledger_ref": self.fibre_ledger_ref,
            "residual_refs": list(_refs(self.residual_refs)),
            "external_proposal_refs": list(_refs(self.external_proposal_refs)),
            "one_proposal_contract": True,
            "one_reduction_authority": True,
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


class IntegratedSemanticProducer:
    """Normalise internal executors into one proposal and fibre contract."""

    def __init__(self, contract: IntegratedProducerContract | None = None):
        self.contract = contract or IntegratedProducerContract()

    def normalise_proposals(
        self,
        proposals: Sequence[FactorProposal],
        *,
        operation_kind: str,
        operation_contract: str,
        sub_executor_ref: str,
        ontology_axis_refs: Iterable[str] = (),
        execution_metadata: Mapping[str, Any] | None = None,
    ) -> tuple[FactorProposal, ...]:
        if operation_kind not in _OPERATION_KINDS:
            raise ValueError("unsupported integrated producer operation")
        fibre_kind = _OPERATION_TO_FIBRE[operation_kind]
        metadata = {
            "sub_executor_ref": sub_executor_ref,
            "operation_kind": operation_kind,
            **dict(execution_metadata or {}),
        }
        return tuple(
            sorted(
                (
                    replace(
                        proposal,
                        producer_contract=self.contract.contract_ref,
                        producer_scope="integrated",
                        operation_contract=operation_contract,
                        fibre_kind=fibre_kind,
                        ontology_axis_refs=_refs(
                            (
                                *proposal.ontology_axis_refs,
                                *tuple(ontology_axis_refs),
                            )
                        ),
                        execution_metadata={
                            **dict(proposal.execution_metadata),
                            **metadata,
                        },
                    )
                    for proposal in proposals
                ),
                key=lambda row: row.proposal_ref,
            )
        )

    def sub_executor_receipt(
        self,
        *,
        document_ref: str,
        operation_kind: str,
        operation_contract: str,
        sub_executor_ref: str,
        declaration_ref: str,
        rule_set_revision: str,
        input_refs: Iterable[str],
        proposals: Sequence[FactorProposal],
        residual_refs: Iterable[str] = (),
        assumptions: Iterable[str] = (),
        metrics: Mapping[str, Any] | None = None,
    ) -> SubExecutorReceipt:
        return SubExecutorReceipt(
            document_ref=document_ref,
            operation_kind=operation_kind,
            operation_contract=operation_contract,
            sub_executor_ref=sub_executor_ref,
            declaration_ref=declaration_ref,
            rule_set_revision=rule_set_revision,
            input_refs=_refs(input_refs),
            proposal_refs=_refs(row.proposal_ref for row in proposals),
            residual_refs=_refs(residual_refs),
            assumptions=_refs(assumptions),
            metrics=dict(metrics or {}),
        )

    def fibre_ledger(
        self,
        *,
        proposals: Sequence[FactorProposal],
        sub_executor_receipts: Sequence[SubExecutorReceipt] = (),
        transports: Sequence[SemanticTransport] = (),
        ontology_axes: Sequence[OntologyAxis] = (),
        axis_obligations: Sequence[AxisObligation] = (),
        boundary_obligations: Sequence[FibreBoundaryObligation] = (),
    ) -> SemanticFibreLedger:
        coordinates: dict[str, SemanticCoordinate] = {}
        elements = []
        proposal_by_ref = {row.proposal_ref: row for row in proposals}
        for proposal in proposals:
            coordinate = SemanticCoordinate(
                document_ref=proposal.document_ref,
                scope_ref=str(proposal.scope_ref),
                source_span_refs=proposal.source_span_refs,
                statement_role=proposal.statement_role,
                factor_family=proposal.factor_type_ref,
                coordinate_kind=proposal.coordinate_kind,
            )
            if coordinate.coordinate_ref != proposal.semantic_coordinate_ref:
                raise ValueError(
                    "proposal coordinate disagrees with canonical coordinate"
                )
            coordinates[coordinate.coordinate_ref] = coordinate
            elements.append(
                fibre_element_from_proposal_row(proposal.to_dict())
            )

        element_ref_by_proposal = {
            row.content_ref: row.element_ref for row in elements
        }
        derivations: list[FibreDerivation] = []
        for receipt in sub_executor_receipts:
            output_refs = tuple(
                element_ref_by_proposal[proposal_ref]
                for proposal_ref in receipt.proposal_refs
                if proposal_ref in element_ref_by_proposal
            )
            derivations.append(
                FibreDerivation(
                    document_ref=receipt.document_ref,
                    operation_kind=receipt.operation_kind,
                    declaration_ref=receipt.declaration_ref,
                    producer_contract=self.contract.contract_ref,
                    input_element_refs=receipt.input_refs,
                    output_element_refs=output_refs,
                    sub_executor_ref=receipt.sub_executor_ref,
                    rule_set_revision=receipt.rule_set_revision,
                    receipt_ref=receipt.receipt_ref,
                    assumptions=receipt.assumptions,
                    metrics=receipt.metrics,
                )
            )
            for proposal_ref in receipt.proposal_refs:
                if proposal_ref not in proposal_by_ref:
                    raise ValueError(
                        "sub-executor receipt refers to unknown proposal"
                    )

        return SemanticFibreLedger(
            coordinates=tuple(
                coordinates[key] for key in sorted(coordinates)
            ),
            elements=tuple(
                sorted(elements, key=lambda row: row.element_ref)
            ),
            transports=tuple(
                sorted(transports, key=lambda row: row.transport_ref)
            ),
            derivations=tuple(
                sorted(derivations, key=lambda row: row.derivation_ref)
            ),
            ontology_axes=tuple(
                sorted(ontology_axes, key=lambda row: row.axis_ref)
            ),
            axis_obligations=tuple(
                sorted(
                    axis_obligations,
                    key=lambda row: row.obligation_ref,
                )
            ),
            boundary_obligations=tuple(
                sorted(
                    boundary_obligations,
                    key=lambda row: row.boundary_ref,
                )
            ),
        )

    def receipt(
        self,
        *,
        document_ref: str,
        proposals: Sequence[FactorProposal],
        fibre_ledger: SemanticFibreLedger,
        sub_executor_receipts: Sequence[SubExecutorReceipt] = (),
        residual_refs: Iterable[str] = (),
    ) -> IntegratedProducerReceipt:
        return IntegratedProducerReceipt(
            document_ref=document_ref,
            contract_ref=self.contract.contract_ref,
            proposal_refs=_refs(row.proposal_ref for row in proposals),
            sub_executor_receipt_refs=_refs(
                row.receipt_ref for row in sub_executor_receipts
            ),
            fibre_ledger_ref=fibre_ledger.ledger_ref,
            residual_refs=_refs(residual_refs),
            external_proposal_refs=_refs(
                row.proposal_ref
                for row in proposals
                if row.producer_scope == "external"
            ),
        )


__all__ = [
    "INTEGRATED_PRODUCER_CONTRACT_SCHEMA_VERSION",
    "INTEGRATED_PRODUCER_RECEIPT_SCHEMA_VERSION",
    "SUB_EXECUTOR_RECEIPT_SCHEMA_VERSION",
    "IntegratedProducerContract",
    "IntegratedProducerReceipt",
    "IntegratedSemanticProducer",
    "ProducerCapability",
    "SubExecutorReceipt",
]
