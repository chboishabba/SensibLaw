"""Immutable document-local PNF proposals and deterministic reduction.

Workers may generate proposals concurrently, but they never mutate a shared graph.
The reducer validates references, orders by canonical keys, deduplicates byte-identical
proposals, and retains incompatible alternatives as explicit residuals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.policy.carriers.canonical import canonical_sha256


FACTOR_PROPOSAL_SCHEMA_VERSION = "sl.pnf.factor_proposal.v0_1"
PROPOSAL_REDUCTION_SCHEMA_VERSION = "sl.pnf.proposal_reduction.v0_1"
CROSS_DOCUMENT_RELATION_SCHEMA_VERSION = "sl.pnf.cross_document_relation.v0_1"


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
            "factor_type_ref": self.factor_type_ref,
            "source_span_refs": sorted(set(self.source_span_refs)),
            "input_observation_refs": sorted(set(self.input_observation_refs)),
            "dependency_factor_refs": sorted(set(self.dependency_factor_refs)),
            "structural_signature": self.structural_signature,
            "role_bindings": dict(sorted(self.role_bindings.items())),
            "qualifier_state": dict(self.qualifier_state),
            "producer_contract": self.producer_contract,
            "declaration_revision": self.declaration_revision,
            "candidate_payload": dict(self.candidate_payload),
            "residuals": sorted(set(self.residuals)),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": FACTOR_PROPOSAL_SCHEMA_VERSION,
            "proposal_ref": self.proposal_ref,
            "proposal_digest": self.proposal_digest,
            **self.identity_payload(),
            "authority": "candidate_only",
        }


@dataclass(frozen=True)
class ReductionResidual:
    residual_ref: str
    document_ref: str
    residual_type: str
    proposal_refs: tuple[str, ...]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReducedFactor:
    factor_ref: str
    document_ref: str
    factor_type_ref: str
    structural_signature: str
    proposal_refs: tuple[str, ...]
    alternatives: tuple[Mapping[str, Any], ...]
    role_bindings: Mapping[str, str]
    qualifier_state: Mapping[str, Any]
    residuals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_ref": self.factor_ref,
            "document_ref": self.document_ref,
            "factor_type_ref": self.factor_type_ref,
            "structural_signature": self.structural_signature,
            "proposal_refs": list(self.proposal_refs),
            "alternatives": [dict(row) for row in self.alternatives],
            "role_bindings": dict(self.role_bindings),
            "qualifier_state": dict(self.qualifier_state),
            "residuals": list(self.residuals),
            "closure_state": "requires_review" if self.residuals else "locally_closed",
        }


@dataclass(frozen=True)
class ProposalReduction:
    document_ref: str
    factors: tuple[ReducedFactor, ...]
    residuals: tuple[ReductionResidual, ...]
    proposal_count: int
    deduplicated_count: int

    @property
    def graph_ref(self) -> str:
        return "pnf-document-graph:" + canonical_sha256(
            {
                "document_ref": self.document_ref,
                "factors": [row.to_dict() for row in self.factors],
                "residuals": [row.to_dict() for row in self.residuals],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROPOSAL_REDUCTION_SCHEMA_VERSION,
            "document_ref": self.document_ref,
            "graph_ref": self.graph_ref,
            "proposal_count": self.proposal_count,
            "deduplicated_count": self.deduplicated_count,
            "factors": [row.to_dict() for row in self.factors],
            "residuals": [row.to_dict() for row in self.residuals],
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


def _compatible(left: FactorProposal, right: FactorProposal) -> bool:
    if left.factor_type_ref != right.factor_type_ref:
        return False
    if left.structural_signature != right.structural_signature:
        return False
    for role in set(left.role_bindings) & set(right.role_bindings):
        if left.role_bindings[role] != right.role_bindings[role]:
            return False
    return True


def reduce_factor_proposals(
    *,
    document_ref: str,
    proposals: Iterable[FactorProposal],
    known_observation_refs: Iterable[str] = (),
    known_dependency_refs: Iterable[str] = (),
) -> ProposalReduction:
    ordered = sorted(proposals, key=lambda row: row.proposal_ref)
    for proposal in ordered:
        if proposal.document_ref != document_ref:
            raise ValueError("cross-document proposal supplied to document-local reducer")

    observation_refs = set(known_observation_refs)
    dependency_refs = set(known_dependency_refs)
    validation_residuals: list[ReductionResidual] = []
    valid: list[FactorProposal] = []
    for proposal in ordered:
        missing_observations = sorted(set(proposal.input_observation_refs) - observation_refs) if observation_refs else []
        missing_dependencies = sorted(set(proposal.dependency_factor_refs) - dependency_refs) if dependency_refs else []
        if missing_observations or missing_dependencies:
            residual_type = "missing_reduction_input"
            residual_ref = "reduction-residual:" + canonical_sha256(
                {
                    "proposal_ref": proposal.proposal_ref,
                    "missing_observations": missing_observations,
                    "missing_dependencies": missing_dependencies,
                }
            )
            validation_residuals.append(
                ReductionResidual(
                    residual_ref=residual_ref,
                    document_ref=document_ref,
                    residual_type=residual_type,
                    proposal_refs=(proposal.proposal_ref,),
                    message="proposal retained outside reduction because declared inputs are unavailable",
                )
            )
            continue
        valid.append(proposal)

    unique = {row.proposal_ref: row for row in valid}
    deduplicated = sorted(unique.values(), key=lambda row: row.proposal_ref)
    groups: list[list[FactorProposal]] = []
    for proposal in deduplicated:
        matched = next((group for group in groups if all(_compatible(proposal, item) for item in group)), None)
        if matched is None:
            groups.append([proposal])
        else:
            matched.append(proposal)

    factors: list[ReducedFactor] = []
    incompatibility_residuals: list[ReductionResidual] = []
    signature_groups: dict[tuple[str, str], list[list[FactorProposal]]] = {}
    for group in groups:
        key = (group[0].factor_type_ref, group[0].structural_signature)
        signature_groups.setdefault(key, []).append(group)

    for key, compatible_groups in sorted(signature_groups.items()):
        if len(compatible_groups) > 1:
            refs = tuple(sorted(row.proposal_ref for group in compatible_groups for row in group))
            incompatibility_residuals.append(
                ReductionResidual(
                    residual_ref="reduction-residual:" + canonical_sha256({"kind": "incompatible_alternatives", "refs": refs}),
                    document_ref=document_ref,
                    residual_type="incompatible_alternatives",
                    proposal_refs=refs,
                    message="structurally related proposals disagree on one or more occupied coordinates",
                )
            )
        for group in compatible_groups:
            proposal_refs = tuple(sorted(row.proposal_ref for row in group))
            roles: dict[str, str] = {}
            qualifiers: dict[str, Any] = {}
            residuals: set[str] = set()
            alternatives: list[Mapping[str, Any]] = []
            for proposal in sorted(group, key=lambda row: row.proposal_ref):
                roles.update(proposal.role_bindings)
                qualifiers.update(proposal.qualifier_state)
                residuals.update(proposal.residuals)
                alternatives.append(dict(proposal.candidate_payload))
            factor_ref = "factor:" + canonical_sha256(
                {
                    "document_ref": document_ref,
                    "factor_type_ref": key[0],
                    "structural_signature": key[1],
                    "proposal_refs": proposal_refs,
                }
            )
            factors.append(
                ReducedFactor(
                    factor_ref=factor_ref,
                    document_ref=document_ref,
                    factor_type_ref=key[0],
                    structural_signature=key[1],
                    proposal_refs=proposal_refs,
                    alternatives=tuple(alternatives),
                    role_bindings=dict(sorted(roles.items())),
                    qualifier_state=qualifiers,
                    residuals=tuple(sorted(residuals)),
                )
            )

    return ProposalReduction(
        document_ref=document_ref,
        factors=tuple(sorted(factors, key=lambda row: row.factor_ref)),
        residuals=tuple(sorted((*validation_residuals, *incompatibility_residuals), key=lambda row: row.residual_ref)),
        proposal_count=len(ordered),
        deduplicated_count=len(valid) - len(deduplicated),
    )


__all__ = [
    "CROSS_DOCUMENT_RELATION_SCHEMA_VERSION",
    "FACTOR_PROPOSAL_SCHEMA_VERSION",
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
