"""Fibred semantic carriers for the integrated PNF compiler.

The base coordinate system records which semantic question is being considered.
Parser observations, hypotheses, composed candidates, constraint findings,
consequences, enrichment evidence, and residuals live as provenance-bearing
fibre elements over those coordinates.  Transports relate coordinates without
silently closing identity, while the deterministic PNF reducer remains the only
materialisation authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from src.policy.carriers.canonical import canonical_sha256


SEMANTIC_COORDINATE_SCHEMA_VERSION = "sl.pnf.semantic_coordinate.v0_1"
SEMANTIC_FIBRE_ELEMENT_SCHEMA_VERSION = "sl.pnf.semantic_fibre_element.v0_1"
SEMANTIC_FIBRE_LEDGER_SCHEMA_VERSION = "sl.pnf.semantic_fibre_ledger.v0_1"
SEMANTIC_TRANSPORT_SCHEMA_VERSION = "sl.pnf.semantic_transport.v0_1"
ONTOLOGY_AXIS_SCHEMA_VERSION = "sl.pnf.ontology_axis.v0_1"
AXIS_OBLIGATION_SCHEMA_VERSION = "sl.pnf.axis_obligation.v0_1"
FIBRE_BOUNDARY_SCHEMA_VERSION = "sl.pnf.fibre_boundary_obligation.v0_1"
FIBRE_DERIVATION_SCHEMA_VERSION = "sl.pnf.fibre_derivation.v0_1"
FIBRE_VALIDATION_SCHEMA_VERSION = "sl.pnf.fibre_validation.v0_1"

_COORDINATE_KINDS = {"object", "morphism", "obligation", "external"}
_FIBRE_KINDS = {
    "observation",
    "hypothesis",
    "composition",
    "constraint",
    "consequence",
    "enrichment",
    "residual",
    "review",
}
_DERIVATION_ROLES = {"support", "contradict", "undetermined", "transport"}
_SUPPORT_STATES = {
    "unscored",
    "candidate",
    "supported",
    "supported_with_residuals",
    "contested",
    "unsupported",
    "unresolved",
}
_TRANSPORT_STRENGTHS = {
    "discoverable",
    "candidate",
    "close",
    "exact",
    "identity",
}
_AXIS_STATES = {
    "open",
    "satisfied",
    "contradicted",
    "both",
    "undetermined",
    "inapplicable",
}
_BOUNDARY_STATES = {"open", "discharged", "external"}
_VALIDATION_OUTCOMES = {
    "satisfied",
    "violated",
    "both",
    "undetermined",
    "inapplicable",
}


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class SemanticCoordinate:
    """One base point over which semantic evidence and alternatives accumulate."""

    document_ref: str
    scope_ref: str
    source_span_refs: tuple[str, ...]
    statement_role: str
    factor_family: str
    coordinate_kind: str = "object"
    source_coordinate_refs: tuple[str, ...] = ()
    target_coordinate_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.coordinate_kind not in _COORDINATE_KINDS:
            raise ValueError("unsupported semantic coordinate kind")
        if not self.document_ref or not self.scope_ref or not self.factor_family:
            raise ValueError("semantic coordinates require document, scope, and family")
        if self.source_span_refs != _refs(self.source_span_refs):
            raise ValueError("source span references must be canonically ordered")

    @property
    def coordinate_ref(self) -> str:
        return "semantic-coordinate:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SEMANTIC_COORDINATE_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "scope_ref": self.scope_ref,
            "source_span_refs": list(self.source_span_refs),
            "statement_role": self.statement_role,
            "factor_family": self.factor_family,
            "coordinate_kind": self.coordinate_kind,
            "source_coordinate_refs": list(_refs(self.source_coordinate_refs)),
            "target_coordinate_refs": list(_refs(self.target_coordinate_refs)),
        }
        if include_ref:
            payload["coordinate_ref"] = self.coordinate_ref
        return payload


@dataclass(frozen=True)
class OntologyAxis:
    """A named, versioned classification subfibration."""

    axis_ref: str
    label: str
    authority_ref: str
    relation_refs: tuple[str, ...]
    root_refs: tuple[str, ...]
    open_world: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ONTOLOGY_AXIS_SCHEMA_VERSION,
            "axis_ref": self.axis_ref,
            "label": self.label,
            "authority_ref": self.authority_ref,
            "relation_refs": list(_refs(self.relation_refs)),
            "root_refs": list(_refs(self.root_refs)),
            "open_world": self.open_world,
        }


@dataclass(frozen=True)
class SemanticTransport:
    """Controlled evidence transport between semantic coordinates or bases."""

    document_ref: str
    source_coordinate_ref: str
    target_coordinate_ref: str
    transport_type: str
    strength: str
    evidence_refs: tuple[str, ...]
    ontology_axis_refs: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ("inspect",)
    residual_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.strength not in _TRANSPORT_STRENGTHS:
            raise ValueError("unsupported semantic transport strength")
        operations = set(self.allowed_operations)
        if self.strength == "discoverable" and "substitute" in operations:
            raise ValueError("discoverable transports cannot permit substitution")
        if not self.source_coordinate_ref or not self.target_coordinate_ref:
            raise ValueError("semantic transport requires source and target")

    @property
    def transport_ref(self) -> str:
        return "semantic-transport:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SEMANTIC_TRANSPORT_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "source_coordinate_ref": self.source_coordinate_ref,
            "target_coordinate_ref": self.target_coordinate_ref,
            "transport_type": self.transport_type,
            "strength": self.strength,
            "evidence_refs": list(_refs(self.evidence_refs)),
            "ontology_axis_refs": list(_refs(self.ontology_axis_refs)),
            "allowed_operations": list(_refs(self.allowed_operations)),
            "residual_refs": list(_refs(self.residual_refs)),
            "identity_closed": False,
            "semantic_state_promoted": False,
        }
        if include_ref:
            payload["transport_ref"] = self.transport_ref
        return payload


@dataclass(frozen=True)
class FibreElement:
    """One provenance-bearing item in the fibre over a semantic coordinate."""

    document_ref: str
    coordinate_ref: str
    fibre_kind: str
    content_ref: str
    derivation_role: str
    producer_contract: str
    operation_contract: str
    source_refs: tuple[str, ...] = ()
    dependency_refs: tuple[str, ...] = ()
    transport_refs: tuple[str, ...] = ()
    ontology_axis_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    coverage_requirements: tuple[str, ...] = ()
    support_state: str = "candidate"
    confidence: float | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    external: bool = False
    execution_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fibre_kind not in _FIBRE_KINDS:
            raise ValueError("unsupported semantic fibre kind")
        if self.derivation_role not in _DERIVATION_ROLES:
            raise ValueError("unsupported fibre derivation role")
        if self.support_state not in _SUPPORT_STATES:
            raise ValueError("unsupported fibre support state")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("fibre confidence must be between zero and one")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "coordinate_ref": self.coordinate_ref,
            "fibre_kind": self.fibre_kind,
            "content_ref": self.content_ref,
            "derivation_role": self.derivation_role,
            "producer_contract": self.producer_contract,
            "operation_contract": self.operation_contract,
            "source_refs": list(_refs(self.source_refs)),
            "dependency_refs": list(_refs(self.dependency_refs)),
            "transport_refs": list(_refs(self.transport_refs)),
            "ontology_axis_refs": list(_refs(self.ontology_axis_refs)),
            "assumptions": list(_refs(self.assumptions)),
            "coverage_requirements": list(_refs(self.coverage_requirements)),
            "support_state": self.support_state,
            "confidence": self.confidence,
            "payload": dict(self.payload),
            "external": self.external,
        }

    @property
    def element_ref(self) -> str:
        return "semantic-fibre-element:" + canonical_sha256(
            self.identity_payload()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SEMANTIC_FIBRE_ELEMENT_SCHEMA_VERSION,
            "element_ref": self.element_ref,
            **self.identity_payload(),
            "execution_metadata": dict(self.execution_metadata),
            "authority": "external_candidate" if self.external else "candidate_only",
        }


@dataclass(frozen=True)
class FibreDerivation:
    """Receipt-bearing derivation between fibre elements."""

    document_ref: str
    operation_kind: str
    declaration_ref: str
    producer_contract: str
    input_element_refs: tuple[str, ...]
    output_element_refs: tuple[str, ...]
    sub_executor_ref: str
    rule_set_revision: str
    receipt_ref: str | None = None
    assumptions: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "operation_kind": self.operation_kind,
            "declaration_ref": self.declaration_ref,
            "producer_contract": self.producer_contract,
            "input_element_refs": list(_refs(self.input_element_refs)),
            "output_element_refs": list(_refs(self.output_element_refs)),
            "sub_executor_ref": self.sub_executor_ref,
            "rule_set_revision": self.rule_set_revision,
            "receipt_ref": self.receipt_ref,
            "assumptions": list(_refs(self.assumptions)),
        }

    @property
    def derivation_ref(self) -> str:
        return "semantic-fibre-derivation:" + canonical_sha256(
            self.identity_payload()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FIBRE_DERIVATION_SCHEMA_VERSION,
            "derivation_ref": self.derivation_ref,
            **self.identity_payload(),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True)
class AxisObligation:
    """Demand for evidence along one named ontology axis."""

    document_ref: str
    coordinate_ref: str
    axis_ref: str
    obligation_type: str
    trigger_refs: tuple[str, ...]
    frontier_refs: tuple[str, ...] = ()
    state: str = "open"
    resource_limit_reached: bool = False

    def __post_init__(self) -> None:
        if self.state not in _AXIS_STATES:
            raise ValueError("unsupported ontology-axis obligation state")

    @property
    def obligation_ref(self) -> str:
        return "semantic-axis-obligation:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": AXIS_OBLIGATION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "coordinate_ref": self.coordinate_ref,
            "axis_ref": self.axis_ref,
            "obligation_type": self.obligation_type,
            "trigger_refs": list(_refs(self.trigger_refs)),
            "frontier_refs": list(_refs(self.frontier_refs)),
            "state": self.state,
            "resource_limit_reached": self.resource_limit_reached,
            "truth_closed": False,
        }
        if include_ref:
            payload["obligation_ref"] = self.obligation_ref
        return payload


@dataclass(frozen=True)
class FibreBoundaryObligation:
    """Boundary data exported by an incomplete, conflicted, or external fibre."""

    document_ref: str
    coordinate_ref: str
    scope_ref: str
    boundary_kind: str
    evidence_refs: tuple[str, ...]
    frontier_refs: tuple[str, ...] = ()
    required_axis_refs: tuple[str, ...] = ()
    state: str = "open"
    message: str = ""

    def __post_init__(self) -> None:
        if self.state not in _BOUNDARY_STATES:
            raise ValueError("unsupported fibre boundary state")

    @property
    def boundary_ref(self) -> str:
        return "semantic-fibre-boundary:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": FIBRE_BOUNDARY_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "coordinate_ref": self.coordinate_ref,
            "scope_ref": self.scope_ref,
            "boundary_kind": self.boundary_kind,
            "evidence_refs": list(_refs(self.evidence_refs)),
            "frontier_refs": list(_refs(self.frontier_refs)),
            "required_axis_refs": list(_refs(self.required_axis_refs)),
            "state": self.state,
            "message": self.message,
        }
        if include_ref:
            payload["boundary_ref"] = self.boundary_ref
        return payload


@dataclass(frozen=True)
class FibreValidation:
    """Five-way validation result derived from one fibre and its coverage."""

    coordinate_ref: str
    outcome: str
    supporting_element_refs: tuple[str, ...]
    contradicting_element_refs: tuple[str, ...]
    undetermined_element_refs: tuple[str, ...]
    residual_refs: tuple[str, ...]
    ontology_axis_refs: tuple[str, ...]
    applicable: bool
    coverage_complete: bool

    def __post_init__(self) -> None:
        if self.outcome not in _VALIDATION_OUTCOMES:
            raise ValueError("unsupported fibre validation outcome")

    @property
    def validation_ref(self) -> str:
        return "semantic-fibre-validation:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": FIBRE_VALIDATION_SCHEMA_VERSION,
            "coordinate_ref": self.coordinate_ref,
            "outcome": self.outcome,
            "supporting_element_refs": list(_refs(self.supporting_element_refs)),
            "contradicting_element_refs": list(
                _refs(self.contradicting_element_refs)
            ),
            "undetermined_element_refs": list(
                _refs(self.undetermined_element_refs)
            ),
            "residual_refs": list(_refs(self.residual_refs)),
            "ontology_axis_refs": list(_refs(self.ontology_axis_refs)),
            "applicable": self.applicable,
            "coverage_complete": self.coverage_complete,
            "truth_closed": False,
        }
        if include_ref:
            payload["validation_ref"] = self.validation_ref
        return payload


def evaluate_fibre(
    *,
    coordinate_ref: str,
    elements: Iterable[FibreElement],
    residual_refs: Iterable[str] = (),
    ontology_axis_refs: Iterable[str] = (),
    applicable: bool = True,
    coverage_complete: bool = False,
) -> FibreValidation:
    rows = tuple(elements)
    supporting = _refs(
        row.element_ref for row in rows if row.derivation_role == "support"
    )
    contradicting = _refs(
        row.element_ref for row in rows if row.derivation_role == "contradict"
    )
    undetermined = _refs(
        row.element_ref for row in rows if row.derivation_role == "undetermined"
    )
    if not applicable:
        outcome = "inapplicable"
    elif supporting and contradicting:
        outcome = "both"
    elif supporting:
        outcome = "satisfied"
    elif contradicting:
        outcome = "violated"
    else:
        outcome = "undetermined"
    return FibreValidation(
        coordinate_ref=coordinate_ref,
        outcome=outcome,
        supporting_element_refs=supporting,
        contradicting_element_refs=contradicting,
        undetermined_element_refs=undetermined,
        residual_refs=_refs(residual_refs),
        ontology_axis_refs=_refs(ontology_axis_refs),
        applicable=applicable,
        coverage_complete=coverage_complete,
    )


@dataclass(frozen=True)
class SemanticFibreLedger:
    """ACI ledger of the fibred semantic state beneath deterministic reduction."""

    coordinates: tuple[SemanticCoordinate, ...] = ()
    elements: tuple[FibreElement, ...] = ()
    transports: tuple[SemanticTransport, ...] = ()
    derivations: tuple[FibreDerivation, ...] = ()
    ontology_axes: tuple[OntologyAxis, ...] = ()
    axis_obligations: tuple[AxisObligation, ...] = ()
    boundary_obligations: tuple[FibreBoundaryObligation, ...] = ()

    def join(self, other: "SemanticFibreLedger") -> "SemanticFibreLedger":
        coordinates = {
            row.coordinate_ref: row for row in (*self.coordinates, *other.coordinates)
        }
        elements = {
            row.element_ref: row for row in (*self.elements, *other.elements)
        }
        transports = {
            row.transport_ref: row for row in (*self.transports, *other.transports)
        }
        derivations = {
            row.derivation_ref: row
            for row in (*self.derivations, *other.derivations)
        }
        axes = {row.axis_ref: row for row in (*self.ontology_axes, *other.ontology_axes)}
        axis_obligations = {
            row.obligation_ref: row
            for row in (*self.axis_obligations, *other.axis_obligations)
        }
        boundaries = {
            row.boundary_ref: row
            for row in (*self.boundary_obligations, *other.boundary_obligations)
        }
        return SemanticFibreLedger(
            coordinates=tuple(coordinates[key] for key in sorted(coordinates)),
            elements=tuple(elements[key] for key in sorted(elements)),
            transports=tuple(transports[key] for key in sorted(transports)),
            derivations=tuple(derivations[key] for key in sorted(derivations)),
            ontology_axes=tuple(axes[key] for key in sorted(axes)),
            axis_obligations=tuple(
                axis_obligations[key] for key in sorted(axis_obligations)
            ),
            boundary_obligations=tuple(
                boundaries[key] for key in sorted(boundaries)
            ),
        )

    def fibre(self, coordinate_ref: str) -> tuple[FibreElement, ...]:
        return tuple(
            row for row in self.elements if row.coordinate_ref == coordinate_ref
        )

    @property
    def ledger_ref(self) -> str:
        return "semantic-fibre-ledger:" + canonical_sha256(
            self.to_dict(include_ref=False)
        )

    def to_dict(self, *, include_ref: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": SEMANTIC_FIBRE_LEDGER_SCHEMA_VERSION,
            "coordinates": [row.to_dict() for row in self.coordinates],
            "elements": [row.to_dict() for row in self.elements],
            "transports": [row.to_dict() for row in self.transports],
            "derivations": [row.to_dict() for row in self.derivations],
            "ontology_axes": [row.to_dict() for row in self.ontology_axes],
            "axis_obligations": [
                row.to_dict() for row in self.axis_obligations
            ],
            "boundary_obligations": [
                row.to_dict() for row in self.boundary_obligations
            ],
            "merge_properties": ["associative", "commutative", "idempotent"],
            "identity_promoted": False,
            "legal_truth_closed": False,
        }
        if include_ref:
            payload["ledger_ref"] = self.ledger_ref
        return payload


def fibre_element_from_proposal_row(
    proposal: Mapping[str, Any],
    *,
    execution_metadata: Mapping[str, Any] | None = None,
) -> FibreElement:
    return FibreElement(
        document_ref=str(proposal["document_ref"]),
        coordinate_ref=str(proposal["semantic_coordinate_ref"]),
        fibre_kind=str(proposal.get("fibre_kind") or "hypothesis"),
        content_ref=str(proposal["proposal_ref"]),
        derivation_role=str(proposal.get("derivation_role") or "support"),
        producer_contract=str(proposal["producer_contract"]),
        operation_contract=str(proposal.get("operation_contract") or ""),
        source_refs=tuple(
            str(ref)
            for ref in (
                *(proposal.get("source_span_refs") or ()),
                *(proposal.get("input_observation_refs") or ()),
            )
        ),
        dependency_refs=tuple(
            str(ref) for ref in proposal.get("dependency_factor_refs") or ()
        ),
        transport_refs=tuple(
            str(ref) for ref in proposal.get("transport_refs") or ()
        ),
        ontology_axis_refs=tuple(
            str(ref) for ref in proposal.get("ontology_axis_refs") or ()
        ),
        assumptions=tuple(str(ref) for ref in proposal.get("assumptions") or ()),
        coverage_requirements=tuple(
            str(ref) for ref in proposal.get("coverage_requirements") or ()
        ),
        support_state=str(proposal.get("support_state") or "candidate"),
        confidence=(
            float(proposal["confidence"])
            if proposal.get("confidence") is not None
            else None
        ),
        payload=dict(proposal.get("candidate_payload") or {}),
        external=str(proposal.get("producer_scope") or "integrated") == "external",
        execution_metadata=dict(
            execution_metadata or proposal.get("execution_metadata") or {}
        ),
    )


__all__ = [
    "AXIS_OBLIGATION_SCHEMA_VERSION",
    "AxisObligation",
    "FIBRE_BOUNDARY_SCHEMA_VERSION",
    "FIBRE_DERIVATION_SCHEMA_VERSION",
    "FIBRE_VALIDATION_SCHEMA_VERSION",
    "FibreBoundaryObligation",
    "FibreDerivation",
    "FibreElement",
    "FibreValidation",
    "ONTOLOGY_AXIS_SCHEMA_VERSION",
    "OntologyAxis",
    "SEMANTIC_COORDINATE_SCHEMA_VERSION",
    "SEMANTIC_FIBRE_ELEMENT_SCHEMA_VERSION",
    "SEMANTIC_FIBRE_LEDGER_SCHEMA_VERSION",
    "SEMANTIC_TRANSPORT_SCHEMA_VERSION",
    "SemanticCoordinate",
    "SemanticFibreLedger",
    "SemanticTransport",
    "evaluate_fibre",
    "fibre_element_from_proposal_row",
]
