"""Declared, lossy Domain IR contracts and receipt carriers.

Domain IR is an operational quotient of resolved PNF. Projection contracts
state what they preserve, forget, and require. Missing coordinates return PNF
resolution demands instead of being guessed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from src.policy.carriers.canonical import canonical_sha256

DOMAIN_IR_CONTRACT_SCHEMA_VERSION = "sl.pnf.domain_ir_contract.v0_1"
DOMAIN_IR_PROJECTION_SCHEMA_VERSION = "sl.pnf.domain_ir_projection.v0_1"
DOMAIN_IR_PROJECTION_RECEIPT_SCHEMA_VERSION = (
    "sl.pnf.domain_ir_projection_receipt.v0_1"
)
PROJECTION_LOSS_RECEIPT_SCHEMA_VERSION = (
    "sl.pnf.projection_loss_receipt.v0_1"
)
PROJECTION_DEMAND_SCHEMA_VERSION = "sl.pnf.projection_demand.v0_1"
DOMAIN_IR_BUILD_SCHEMA_VERSION = "sl.pnf.domain_ir_build.v0_1"

_DOMAINS = {"legal", "timeline", "retrieval"}
_PROJECTION_STATES = {"projected", "blocked", "inapplicable"}


def refs(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class DomainIRProjectionContract:
    domain: str
    accepted_factor_families: tuple[str, ...]
    required_ontology_axis_refs: tuple[str, ...]
    required_statement_roles: tuple[str, ...]
    preserved_fields: tuple[str, ...]
    forgotten_fields: tuple[str, ...]
    authority_ceiling: str
    residual_policy: str
    contract_revision: str = "v0_1"

    def __post_init__(self) -> None:
        if self.domain not in _DOMAINS:
            raise ValueError("unsupported Domain IR projection domain")

    @property
    def contract_ref(self) -> str:
        return "domain-ir-contract:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def accepts(self, factor_type: str) -> bool:
        return any(
            family == "*"
            or (
                family.endswith(".*")
                and factor_type.startswith(family[:-1])
            )
            or family == factor_type
            for family in self.accepted_factor_families
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": DOMAIN_IR_CONTRACT_SCHEMA_VERSION,
            **asdict(self),
            "accepted_factor_families": list(
                refs(self.accepted_factor_families)
            ),
            "required_ontology_axis_refs": list(
                refs(self.required_ontology_axis_refs)
            ),
            "required_statement_roles": list(
                refs(self.required_statement_roles)
            ),
            "preserved_fields": list(refs(self.preserved_fields)),
            "forgotten_fields": list(refs(self.forgotten_fields)),
            "projection_adds_world_truth": False,
        }
        if include_ref:
            payload["contract_ref"] = self.contract_ref
        return payload


@dataclass(frozen=True)
class ProjectionDemand:
    document_ref: str
    domain: str
    resolution_ref: str
    source_factor_ref: str
    structural_signature_ref: str
    demand_kind: str
    required_refs: tuple[str, ...]
    observed_refs: tuple[str, ...]
    message: str
    priority: int = 50

    @property
    def demand_ref(self) -> str:
        return "pnf-projection-demand:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_resolution_demand(self) -> dict[str, Any]:
        facets = {
            f"projection.domain:{self.domain}",
            f"projection.required:{self.demand_kind}",
        }
        if self.domain == "legal":
            facets.add("legal.interpretation_unresolved")
        return {
            "demand_ref": self.demand_ref,
            "document_ref": self.document_ref,
            "factor_ref": self.source_factor_ref,
            "factor_revision_ref": self.source_factor_ref,
            "origin_pnf_ref": self.source_factor_ref,
            "structural_signature_ref": self.structural_signature_ref,
            "subject_kind": "domain_ir_projection",
            "formal_role": self.domain,
            "scope_ref": "document_local",
            "requested_facets": sorted(facets),
            "priority": self.priority,
            "projection_domain": self.domain,
            "projection_demand_kind": self.demand_kind,
            "required_refs": list(refs(self.required_refs)),
            "observed_refs": list(refs(self.observed_refs)),
            "provenance_refs": [self.resolution_ref],
            "authority": "projection_demand_only",
            "semantic_state_promoted": False,
        }

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": PROJECTION_DEMAND_SCHEMA_VERSION,
            **asdict(self),
            "required_refs": list(refs(self.required_refs)),
            "observed_refs": list(refs(self.observed_refs)),
            "authority": "projection_demand_only",
            "semantic_state_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["demand_ref"] = self.demand_ref
        return payload


@dataclass(frozen=True)
class ProjectionLossReceipt:
    document_ref: str
    domain: str
    source_resolution_ref: str
    projection_contract_ref: str
    preserved_fields: tuple[str, ...]
    forgotten_fields: tuple[str, ...]
    source_residual_refs: tuple[str, ...]

    @property
    def loss_ref(self) -> str:
        return "projection-loss:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": PROJECTION_LOSS_RECEIPT_SCHEMA_VERSION,
            **asdict(self),
            "preserved_fields": list(refs(self.preserved_fields)),
            "forgotten_fields": list(refs(self.forgotten_fields)),
            "source_residual_refs": list(refs(self.source_residual_refs)),
            "equal_ir_does_not_imply_equal_pnf": True,
            "semantic_state_promoted": False,
        }
        if include_ref:
            payload["loss_ref"] = self.loss_ref
        return payload


@dataclass(frozen=True)
class DomainIRProjectionReceipt:
    document_ref: str
    domain: str
    source_resolution_ref: str
    source_factor_ref: str
    projection_contract_ref: str
    state: str
    selected_proposal_ref: str | None
    demand_refs: tuple[str, ...]
    loss_ref: str | None
    reason_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.state not in _PROJECTION_STATES:
            raise ValueError("unsupported Domain IR projection state")

    @property
    def receipt_ref(self) -> str:
        return "domain-ir-projection-receipt:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": DOMAIN_IR_PROJECTION_RECEIPT_SCHEMA_VERSION,
            **asdict(self),
            "demand_refs": list(refs(self.demand_refs)),
            "reason_refs": list(refs(self.reason_refs)),
            "authority": "projection_only",
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["receipt_ref"] = self.receipt_ref
        return payload


@dataclass(frozen=True)
class DomainIRProjection:
    document_ref: str
    domain: str
    source_resolution_ref: str
    source_factor_ref: str
    selected_proposal_ref: str
    structural_signature_ref: str
    projection_contract_ref: str
    projection_receipt_ref: str
    loss_ref: str
    payload: Mapping[str, Any]
    provenance_refs: tuple[str, ...]
    residual_refs: tuple[str, ...]
    validation_state: str = "operational_candidate"

    @property
    def domain_ir_ref(self) -> str:
        return f"{self.domain}-ir:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": DOMAIN_IR_PROJECTION_SCHEMA_VERSION,
            **asdict(self),
            "payload": dict(self.payload),
            "provenance_refs": list(refs(self.provenance_refs)),
            "residual_refs": list(refs(self.residual_refs)),
            "authority": "domain_ir_projection_only",
            "identity_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["domain_ir_ref"] = self.domain_ir_ref
        return payload


@dataclass(frozen=True)
class DomainIRProjectionResult:
    contract: DomainIRProjectionContract
    projection: DomainIRProjection | None
    receipt: DomainIRProjectionReceipt
    loss: ProjectionLossReceipt | None
    demands: tuple[ProjectionDemand, ...]


@dataclass(frozen=True)
class DomainIRBuild:
    document_ref: str
    contracts: tuple[DomainIRProjectionContract, ...]
    projections: tuple[DomainIRProjection, ...]
    receipts: tuple[DomainIRProjectionReceipt, ...]
    losses: tuple[ProjectionLossReceipt, ...]
    demands: tuple[ProjectionDemand, ...]

    @property
    def build_ref(self) -> str:
        return "domain-ir-build:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": DOMAIN_IR_BUILD_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "contracts": [row.to_dict() for row in self.contracts],
            "projections": [row.to_dict() for row in self.projections],
            "receipts": [row.to_dict() for row in self.receipts],
            "losses": [row.to_dict() for row in self.losses],
            "demands": [row.to_dict() for row in self.demands],
            "memory_projection_included": False,
            "nashi_projection_included": False,
            "semantic_state_promoted": False,
            "applicability_closed": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["build_ref"] = self.build_ref
        return payload


__all__ = [
    "DomainIRBuild",
    "DomainIRProjection",
    "DomainIRProjectionContract",
    "DomainIRProjectionReceipt",
    "DomainIRProjectionResult",
    "ProjectionDemand",
    "ProjectionLossReceipt",
    "refs",
]
