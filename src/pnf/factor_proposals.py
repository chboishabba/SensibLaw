"""Immutable fibred PNF proposals and deterministic reduction.

Ordinary compiler operations are normalised under one integrated semantic
producer family. Executor details stay outside semantic identity. Proposals are
partitioned by their complete fibre signature before compatibility grouping, so
unrelated fibres never enter the comparison loop.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import comb
from typing import Any, Iterable, Mapping, Sequence

from src.pnf.semantic_fibres import SemanticCoordinate
from src.policy.carriers.canonical import canonical_sha256

INTEGRATED_SEMANTIC_PRODUCER_CONTRACT = "integrated-semantic-producer:v0_1"
FACTOR_PROPOSAL_SCHEMA_VERSION = "sl.pnf.factor_proposal.v0_2"
PROPOSAL_REDUCTION_SCHEMA_VERSION = "sl.pnf.proposal_reduction.v0_3"
CROSS_DOCUMENT_RELATION_SCHEMA_VERSION = "sl.pnf.cross_document_relation.v0_1"

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
_PRODUCER_SCOPES = {"integrated", "external"}
_SUPPORT_STATES = {
    "unscored",
    "candidate",
    "supported",
    "supported_with_residuals",
    "contested",
    "unsupported",
    "unresolved",
}


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@dataclass(frozen=True)
class CompositionDeclaration:
    producer_ref: str
    requires: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    declaration_revision: str = "v0_1"

    @property
    def declaration_ref(self) -> str:
        return "composition-declaration:" + canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer_ref": self.producer_ref,
            "requires": sorted(set(self.requires)),
            "optional": sorted(set(self.optional)),
            "emits": sorted(set(self.emits)),
            "declaration_revision": self.declaration_revision,
        }


@dataclass(frozen=True)
class FactorProposal:
    """One immutable candidate in the fibre over a semantic coordinate."""

    document_ref: str
    source_revision_ref: str
    factor_type_ref: str
    source_span_refs: tuple[str, ...]
    input_observation_refs: tuple[str, ...]
    dependency_factor_refs: tuple[str, ...]
    structural_signature: str
    role_bindings: Mapping[str, str]
    qualifier_state: Mapping[str, Any]
    producer_contract: str
    declaration_revision: str
    candidate_payload: Mapping[str, Any]
    residuals: tuple[str, ...] = ()
    scope_ref: str | None = None
    statement_role: str = "main"
    coordinate_kind: str = "object"
    semantic_coordinate_ref: str | None = None
    fibre_kind: str = "hypothesis"
    derivation_role: str = "support"
    producer_scope: str = "integrated"
    operation_contract: str | None = None
    ontology_axis_refs: tuple[str, ...] = ()
    transport_refs: tuple[str, ...] = ()
    support_state: str = "candidate"
    confidence: float | None = None
    assumptions: tuple[str, ...] = ()
    coverage_requirements: tuple[str, ...] = ()
    execution_metadata: Mapping[str, Any] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if not self.document_ref or not self.factor_type_ref:
            raise ValueError("factor proposal requires document and factor type")
        if self.fibre_kind not in _FIBRE_KINDS:
            raise ValueError("unsupported proposal fibre kind")
        if self.derivation_role not in _DERIVATION_ROLES:
            raise ValueError("unsupported proposal derivation role")
        if self.producer_scope not in _PRODUCER_SCOPES:
            raise ValueError("unsupported proposal producer scope")
        if self.support_state not in _SUPPORT_STATES:
            raise ValueError("unsupported proposal support state")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposal confidence must be between zero and one")

        spans = _refs(self.source_span_refs)
        observations = _refs(self.input_observation_refs)
        dependencies = _refs(self.dependency_factor_refs)
        residuals = _refs(self.residuals)
        axes = _refs(self.ontology_axis_refs)
        transports = _refs(self.transport_refs)
        assumptions = _refs(self.assumptions)
        coverage = _refs(self.coverage_requirements)
        object.__setattr__(self, "source_span_refs", spans)
        object.__setattr__(self, "input_observation_refs", observations)
        object.__setattr__(self, "dependency_factor_refs", dependencies)
        object.__setattr__(self, "residuals", residuals)
        object.__setattr__(self, "ontology_axis_refs", axes)
        object.__setattr__(self, "transport_refs", transports)
        object.__setattr__(self, "assumptions", assumptions)
        object.__setattr__(self, "coverage_requirements", coverage)

        resolved_scope = self.scope_ref or (min(spans) if spans else "document-global")
        object.__setattr__(self, "scope_ref", resolved_scope)
        operation_contract = self.operation_contract or self.producer_contract
        producer_contract = self.producer_contract
        if self.producer_scope == "integrated":
            producer_contract = INTEGRATED_SEMANTIC_PRODUCER_CONTRACT
        object.__setattr__(self, "operation_contract", operation_contract)
        object.__setattr__(self, "producer_contract", producer_contract)

        coordinate = SemanticCoordinate(
            document_ref=self.document_ref,
            scope_ref=resolved_scope,
            source_span_refs=spans,
            statement_role=self.statement_role,
            factor_family=self.factor_type_ref,
            coordinate_kind=self.coordinate_kind,
        )
        object.__setattr__(
            self,
            "semantic_coordinate_ref",
            self.semantic_coordinate_ref or coordinate.coordinate_ref,
        )

    @property
    def proposal_digest(self) -> str:
        return canonical_sha256(self.identity_payload())

    @property
    def proposal_ref(self) -> str:
        return "factor-proposal:" + self.proposal_digest

    def identity_payload(self) -> dict[str, Any]:
        return {
            "document_ref": self.document_ref,
            "source_revision_ref": self.source_revision_ref,
            "semantic_coordinate_ref": self.semantic_coordinate_ref,
            "scope_ref": self.scope_ref,
            "statement_role": self.statement_role,
            "coordinate_kind": self.coordinate_kind,
            "fibre_kind": self.fibre_kind,
            "derivation_role": self.derivation_role,
            "factor_type_ref": self.factor_type_ref,
            "source_span_refs": list(self.source_span_refs),
            "input_observation_refs": list(self.input_observation_refs),
            "dependency_factor_refs": list(self.dependency_factor_refs),
            "structural_signature": self.structural_signature,
            "role_bindings": dict(sorted(self.role_bindings.items())),
            "qualifier_state": dict(self.qualifier_state),
            "producer_contract": self.producer_contract,
            "producer_scope": self.producer_scope,
            "operation_contract": self.operation_contract,
            "declaration_revision": self.declaration_revision,
            "ontology_axis_refs": list(self.ontology_axis_refs),
            "transport_refs": list(self.transport_refs),
            "support_state": self.support_state,
            "confidence": self.confidence,
            "assumptions": list(self.assumptions),
            "coverage_requirements": list(self.coverage_requirements),
            "candidate_payload": dict(self.candidate_payload),
            "residuals": list(self.residuals),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FACTOR_PROPOSAL_SCHEMA_VERSION,
            "proposal_ref": self.proposal_ref,
            "proposal_digest": self.proposal_digest,
            **self.identity_payload(),
            "execution_metadata": dict(self.execution_metadata),
            "authority": (
                "external_candidate"
                if self.producer_scope == "external"
                else "candidate_only"
            ),
        }


@dataclass(frozen=True)
class ReductionResidual:
    residual_ref: str
    document_ref: str
    residual_type: str
    proposal_refs: tuple[str, ...]
    message: str
    semantic_coordinate_ref: str | None = None
    boundary_kind: str = "fibre"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReducedFactor:
    factor_ref: str
    document_ref: str
    semantic_coordinate_ref: str
    fibre_kind: str
    factor_type_ref: str
    structural_signature: str
    proposal_refs: tuple[str, ...]
    alternatives: tuple[Mapping[str, Any], ...]
    role_bindings: Mapping[str, str]
    qualifier_state: Mapping[str, Any]
    residuals: tuple[str, ...]
    derivation_roles: tuple[str, ...] = ()
    ontology_axis_refs: tuple[str, ...] = ()
    transport_refs: tuple[str, ...] = ()
    support_states: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_ref": self.factor_ref,
            "document_ref": self.document_ref,
            "semantic_coordinate_ref": self.semantic_coordinate_ref,
            "fibre_kind": self.fibre_kind,
            "factor_type_ref": self.factor_type_ref,
            "structural_signature": self.structural_signature,
            "proposal_refs": list(self.proposal_refs),
            "alternatives": [dict(row) for row in self.alternatives],
            "role_bindings": dict(self.role_bindings),
            "qualifier_state": dict(self.qualifier_state),
            "residuals": list(self.residuals),
            "derivation_roles": list(self.derivation_roles),
            "ontology_axis_refs": list(self.ontology_axis_refs),
            "transport_refs": list(self.transport_refs),
            "support_states": list(self.support_states),
            "closure_state": "requires_review" if self.residuals else "locally_closed",
        }


@dataclass(frozen=True)
class ProposalReduction:
    document_ref: str
    factors: tuple[ReducedFactor, ...]
    residuals: tuple[ReductionResidual, ...]
    proposal_count: int
    deduplicated_count: int
    metrics: Mapping[str, Any] = field(default_factory=dict)

    @property
    def graph_ref(self) -> str:
        return "pnf-document-graph:" + canonical_sha256(
            {
                "document_ref": self.document_ref,
                "factors": [row.to_dict() for row in self.factors],
                "residuals": [row.to_dict() for row in self.residuals],
                "reduction_contract": "deterministic-fibrewise-pnf:v0_1",
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROPOSAL_REDUCTION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "graph_ref": self.graph_ref,
            "proposal_count": self.proposal_count,
            "deduplicated_count": self.deduplicated_count,
            "semantic_coordinate_refs": sorted(
                {row.semantic_coordinate_ref for row in self.factors}
            ),
            "factors": [row.to_dict() for row in self.factors],
            "residuals": [row.to_dict() for row in self.residuals],
            "metrics": dict(self.metrics),
            "reduction_contract": "deterministic-fibrewise-pnf:v0_1",
            "integrated_producer_contract": INTEGRATED_SEMANTIC_PRODUCER_CONTRACT,
            "fibrewise_reduction": True,
            "identity_promoted": False,
            "legal_truth_closed": False,
        }


@dataclass(frozen=True)
class CrossDocumentRelation:
    relation_type: str
    source_document_ref: str
    target_document_ref: str
    source_coordinate_refs: tuple[str, ...]
    target_coordinate_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    qualifier_state: Mapping[str, Any] = field(default_factory=dict)
    residuals: tuple[str, ...] = ()

    @property
    def relation_ref(self) -> str:
        return "cross-document-relation:" + canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "source_document_ref": self.source_document_ref,
            "target_document_ref": self.target_document_ref,
            "source_coordinate_refs": sorted(set(self.source_coordinate_refs)),
            "target_coordinate_refs": sorted(set(self.target_coordinate_refs)),
            "evidence_refs": sorted(set(self.evidence_refs)),
            "qualifier_state": dict(self.qualifier_state),
            "residuals": sorted(set(self.residuals)),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CROSS_DOCUMENT_RELATION_SCHEMA_VERSION,
            "relation_ref": self.relation_ref,
            **self.identity_payload(),
            "identity_closed": False,
            "legal_conclusion_promoted": False,
        }


def proposal_build_key(
    *,
    canonical_text_digest: str,
    producer_contract: str,
    declaration_revision: str,
    input_observation_digests: Sequence[str],
    dependency_factor_digests: Sequence[str],
) -> str:
    return canonical_sha256(
        {
            "canonical_text_digest": canonical_text_digest,
            "producer_contract": producer_contract,
            "declaration_revision": declaration_revision,
            "input_observation_digests": sorted(set(input_observation_digests)),
            "dependency_factor_digests": sorted(set(dependency_factor_digests)),
        }
    )


def _signature_key(proposal: FactorProposal) -> tuple[str, str, str, str]:
    return (
        str(proposal.semantic_coordinate_ref),
        proposal.fibre_kind,
        proposal.factor_type_ref,
        proposal.structural_signature,
    )


def _compatible(left: FactorProposal, right: FactorProposal) -> bool:
    if _signature_key(left) != _signature_key(right):
        return False
    return all(
        left.role_bindings[role] == right.role_bindings[role]
        for role in set(left.role_bindings) & set(right.role_bindings)
    )


def reduce_factor_proposals(
    *,
    document_ref: str,
    proposals: Iterable[FactorProposal],
    known_observation_refs: Iterable[str] = (),
    known_dependency_refs: Iterable[str] = (),
) -> ProposalReduction:
    """Materialise canonical summaries independently for each semantic fibre."""

    ordered = sorted(proposals, key=lambda row: row.proposal_ref)
    for proposal in ordered:
        if proposal.document_ref != document_ref:
            raise ValueError("cross-document proposal supplied to document-local reducer")

    observation_refs = set(known_observation_refs)
    dependency_refs = set(known_dependency_refs)
    validation_residuals: list[ReductionResidual] = []
    valid: list[FactorProposal] = []
    for proposal in ordered:
        missing_observations = (
            sorted(set(proposal.input_observation_refs) - observation_refs)
            if observation_refs
            else []
        )
        missing_dependencies = (
            sorted(set(proposal.dependency_factor_refs) - dependency_refs)
            if dependency_refs
            else []
        )
        if missing_observations or missing_dependencies:
            residual_ref = "reduction-residual:" + canonical_sha256(
                {
                    "proposal_ref": proposal.proposal_ref,
                    "semantic_coordinate_ref": proposal.semantic_coordinate_ref,
                    "missing_observations": missing_observations,
                    "missing_dependencies": missing_dependencies,
                }
            )
            validation_residuals.append(
                ReductionResidual(
                    residual_ref=residual_ref,
                    document_ref=document_ref,
                    residual_type="missing_reduction_input",
                    proposal_refs=(proposal.proposal_ref,),
                    message=(
                        "proposal retained outside reduction because declared inputs "
                        "are unavailable"
                    ),
                    semantic_coordinate_ref=proposal.semantic_coordinate_ref,
                    boundary_kind="input_frontier",
                )
            )
            continue
        valid.append(proposal)

    unique = {row.proposal_ref: row for row in valid}
    deduplicated = sorted(unique.values(), key=lambda row: row.proposal_ref)
    buckets: dict[tuple[str, str, str, str], list[FactorProposal]] = {}
    for proposal in deduplicated:
        buckets.setdefault(_signature_key(proposal), []).append(proposal)

    candidate_comparisons = 0
    grouped_by_signature: dict[
        tuple[str, str, str, str], list[list[FactorProposal]]
    ] = {}
    for key, bucket in sorted(buckets.items()):
        groups: list[list[FactorProposal]] = []
        for proposal in bucket:
            matched: list[FactorProposal] | None = None
            for group in groups:
                candidate_comparisons += 1
                if all(_compatible(proposal, item) for item in group):
                    matched = group
                    break
            if matched is None:
                groups.append([proposal])
            else:
                matched.append(proposal)
        grouped_by_signature[key] = groups

    factors: list[ReducedFactor] = []
    incompatibility_residuals: list[ReductionResidual] = []
    for key, compatible_groups in sorted(grouped_by_signature.items()):
        if len(compatible_groups) > 1:
            refs = tuple(
                sorted(
                    row.proposal_ref
                    for group in compatible_groups
                    for row in group
                )
            )
            incompatibility_residuals.append(
                ReductionResidual(
                    residual_ref="reduction-residual:"
                    + canonical_sha256(
                        {
                            "kind": "incompatible_alternatives",
                            "semantic_coordinate_ref": key[0],
                            "refs": refs,
                        }
                    ),
                    document_ref=document_ref,
                    residual_type="incompatible_alternatives",
                    proposal_refs=refs,
                    message=(
                        "proposals in one semantic fibre disagree on one or more "
                        "occupied coordinates"
                    ),
                    semantic_coordinate_ref=key[0],
                    boundary_kind="conflicted_fibre",
                )
            )
        for group in compatible_groups:
            proposal_refs = tuple(sorted(row.proposal_ref for row in group))
            roles: dict[str, str] = {}
            qualifiers: dict[str, Any] = {}
            residuals: set[str] = set()
            alternatives: list[Mapping[str, Any]] = []
            derivation_roles: set[str] = set()
            axes: set[str] = set()
            transports: set[str] = set()
            support_states: set[str] = set()
            for proposal in sorted(group, key=lambda row: row.proposal_ref):
                roles.update(proposal.role_bindings)
                qualifiers.update(proposal.qualifier_state)
                residuals.update(proposal.residuals)
                derivation_roles.add(proposal.derivation_role)
                axes.update(proposal.ontology_axis_refs)
                transports.update(proposal.transport_refs)
                support_states.add(proposal.support_state)
                alternatives.append(
                    {
                        **dict(proposal.candidate_payload),
                        "proposal_ref": proposal.proposal_ref,
                        "derivation_role": proposal.derivation_role,
                        "support_state": proposal.support_state,
                        "confidence": proposal.confidence,
                    }
                )
            factor_ref = "factor:" + canonical_sha256(
                {
                    "document_ref": document_ref,
                    "semantic_coordinate_ref": key[0],
                    "fibre_kind": key[1],
                    "factor_type_ref": key[2],
                    "structural_signature": key[3],
                    "proposal_refs": proposal_refs,
                }
            )
            factors.append(
                ReducedFactor(
                    factor_ref=factor_ref,
                    document_ref=document_ref,
                    semantic_coordinate_ref=key[0],
                    fibre_kind=key[1],
                    factor_type_ref=key[2],
                    structural_signature=key[3],
                    proposal_refs=proposal_refs,
                    alternatives=tuple(alternatives),
                    role_bindings=dict(sorted(roles.items())),
                    qualifier_state=qualifiers,
                    residuals=tuple(sorted(residuals)),
                    derivation_roles=tuple(sorted(derivation_roles)),
                    ontology_axis_refs=tuple(sorted(axes)),
                    transport_refs=tuple(sorted(transports)),
                    support_states=tuple(sorted(support_states)),
                )
            )

    possible_comparisons = comb(len(deduplicated), 2) if len(deduplicated) > 1 else 0
    avoided = max(0, possible_comparisons - candidate_comparisons)
    metrics = {
        "bucket_count": len(buckets),
        "largest_bucket": max((len(value) for value in buckets.values()), default=0),
        "candidate_comparisons": candidate_comparisons,
        "potential_candidate_comparisons": possible_comparisons,
        "comparisons_avoided": avoided,
        "comparison_avoidance_ratio": (
            avoided / possible_comparisons if possible_comparisons else 1.0
        ),
        "duplicates_collapsed": len(valid) - len(deduplicated),
        "alternatives_retained": sum(
            len(group) for groups in grouped_by_signature.values() for group in groups
        ),
        "factor_count": len(factors),
        "reduction_ratio": (
            len(factors) / len(deduplicated) if deduplicated else 0.0
        ),
    }
    return ProposalReduction(
        document_ref=document_ref,
        factors=tuple(sorted(factors, key=lambda row: row.factor_ref)),
        residuals=tuple(
            sorted(
                (*validation_residuals, *incompatibility_residuals),
                key=lambda row: row.residual_ref,
            )
        ),
        proposal_count=len(ordered),
        deduplicated_count=len(valid) - len(deduplicated),
        metrics=metrics,
    )


__all__ = [
    "CROSS_DOCUMENT_RELATION_SCHEMA_VERSION",
    "FACTOR_PROPOSAL_SCHEMA_VERSION",
    "INTEGRATED_SEMANTIC_PRODUCER_CONTRACT",
    "PROPOSAL_REDUCTION_SCHEMA_VERSION",
    "CompositionDeclaration",
    "CrossDocumentRelation",
    "FactorProposal",
    "ProposalReduction",
    "ReducedFactor",
    "ReductionResidual",
    "proposal_build_key",
    "reduce_factor_proposals",
]
