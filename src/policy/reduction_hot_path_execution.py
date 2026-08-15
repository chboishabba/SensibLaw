"""Execution-equivalent bitset acceleration for fibre compatibility reduction.

The canonical reducer groups proposals in ascending ``proposal_ref`` order and
places each proposal into the first existing group whose occupied role bindings
do not conflict. The legacy implementation finds that group by scanning every
existing group and every proposal role.

This module computes the *same first compatible group* using Python integer
bitsets. For every role and role/value pair we maintain a mask of groups that
occupy it. A candidate conflicts with a group exactly when that group occupies
one of the candidate's roles with a different value. The least-significant set
bit of the compatible mask is therefore exactly the first group the canonical
scan would have selected.

Only physical search changes. Proposal order, validation, grouping, factor and
residual identities, metrics describing the canonical comparison order, and
semantic outputs remain unchanged.
"""

from __future__ import annotations

from math import comb
from typing import Any, Iterable, Mapping

from src.pnf.factor_proposals import (
    FactorProposal,
    ProposalReduction,
    ReducedFactor,
    ReductionResidual,
)
from src.policy.carriers.canonical import canonical_sha256


_INSTALL_MARKER = "_reduction_hot_path_execution_installed"


def _signature_key(proposal: FactorProposal) -> tuple[str, str, str, str]:
    return (
        str(proposal.semantic_coordinate_ref),
        proposal.fibre_kind,
        proposal.factor_type_ref,
        proposal.structural_signature,
    )


def _first_set_index(mask: int) -> int:
    """Return the zero-based index of the least-significant set bit."""

    return (mask & -mask).bit_length() - 1


def reduce_factor_proposals_bitset(
    *,
    document_ref: str,
    proposals: Iterable[FactorProposal],
    known_observation_refs: Iterable[str] = (),
    known_dependency_refs: Iterable[str] = (),
) -> ProposalReduction:
    """Exact canonical reduction with bitset first-compatible-group lookup."""

    ordered = sorted(proposals, key=lambda row: row.proposal_ref)
    for proposal in ordered:
        if proposal.document_ref != document_ref:
            raise ValueError(
                "cross-document proposal supplied to document-local reducer"
            )

    observation_refs = (
        known_observation_refs
        if isinstance(known_observation_refs, (set, frozenset))
        else set(known_observation_refs)
    )
    dependency_refs = (
        known_dependency_refs
        if isinstance(known_dependency_refs, (set, frozenset))
        else set(known_dependency_refs)
    )
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

    # ``candidate_comparisons`` intentionally retains the exact number the
    # legacy first-match scan would have performed. ``physical_role_bit_checks``
    # records the smaller amount of actual compatibility work performed here.
    candidate_comparisons = 0
    physical_role_bit_checks = 0
    grouped_by_signature: dict[
        tuple[str, str, str, str], list[list[FactorProposal]]
    ] = {}
    for key, bucket in sorted(buckets.items()):
        groups: list[list[FactorProposal]] = []
        group_roles: list[dict[str, str]] = []
        role_masks: dict[str, int] = {}
        role_value_masks: dict[tuple[str, str], int] = {}

        for proposal in bucket:
            group_count = len(groups)
            all_groups_mask = (1 << group_count) - 1
            conflict_mask = 0
            bindings = tuple(proposal.role_bindings.items())
            for role, value in bindings:
                physical_role_bit_checks += 1
                occupied_mask = role_masks.get(role, 0)
                same_value_mask = role_value_masks.get((role, value), 0)
                conflict_mask |= occupied_mask & ~same_value_mask

            compatible_mask = all_groups_mask & ~conflict_mask
            if compatible_mask:
                matched_index = _first_set_index(compatible_mask)
                # The legacy loop tested groups 0..matched_index inclusive.
                candidate_comparisons += matched_index + 1
                groups[matched_index].append(proposal)
                occupied_roles = group_roles[matched_index]
                group_bit = 1 << matched_index
                for role, value in bindings:
                    if role in occupied_roles:
                        # Compatibility already proves the existing value agrees.
                        continue
                    occupied_roles[role] = value
                    role_masks[role] = role_masks.get(role, 0) | group_bit
                    role_value_masks[(role, value)] = (
                        role_value_masks.get((role, value), 0) | group_bit
                    )
            else:
                # The legacy loop examined every prior group before creating one.
                candidate_comparisons += group_count
                matched_index = len(groups)
                groups.append([proposal])
                occupied_roles = dict(proposal.role_bindings)
                group_roles.append(occupied_roles)
                group_bit = 1 << matched_index
                for role, value in occupied_roles.items():
                    role_masks[role] = role_masks.get(role, 0) | group_bit
                    role_value_masks[(role, value)] = (
                        role_value_masks.get((role, value), 0) | group_bit
                    )
        grouped_by_signature[key] = groups

    factors: list[ReducedFactor] = []
    incompatibility_residuals: list[ReductionResidual] = []
    for key, compatible_groups in sorted(grouped_by_signature.items()):
        if len(compatible_groups) > 1:
            refs = tuple(
                sorted(row.proposal_ref for group in compatible_groups for row in group)
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
    physical_group_scan_equivalent = max(0, candidate_comparisons - physical_role_bit_checks)
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
        "reduction_ratio": (len(factors) / len(deduplicated) if deduplicated else 0.0),
        "compatibility_lookup": "exact_first_match_bitset",
        "physical_role_bit_checks": physical_role_bit_checks,
        "legacy_group_scan_work_avoided": physical_group_scan_equivalent,
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


def install_reduction_hot_path_execution() -> bool:
    """Replace physical compatibility lookup without changing reducer outputs."""

    import src.pnf.factor_proposals as factor_proposals
    import src.pnf.bounded_streaming_owner as bounded_owner

    if getattr(factor_proposals, _INSTALL_MARKER, False):
        return False
    factor_proposals.reduce_factor_proposals = reduce_factor_proposals_bitset
    # The bounded owner imported the reducer directly before this strategy is
    # installed; update that captured module global as well.
    bounded_owner.reduce_factor_proposals = reduce_factor_proposals_bitset
    setattr(factor_proposals, _INSTALL_MARKER, True)
    return True


__all__ = [
    "install_reduction_hot_path_execution",
    "reduce_factor_proposals_bitset",
]
