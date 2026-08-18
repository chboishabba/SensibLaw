"""Sparse input-indexed invalidation for bounded semantic-owner reduction.

The canonical proposal reducer remains authoritative. This execution strategy
changes only *which* owner fibres are revisited when an explicitly declared
input becomes available or unavailable.

Proposal admission records exact reverse indexes

    dependency factor ref -> owners whose proposals require it
    observation ref       -> owners whose proposals require it

and reduction follows only those edges to a local fixed point. No whole-owner
scan is used to discover dependent fibres.

The wrapper deliberately does not assume same-owner reduction is associative or
append-homomorphic. Each woken owner is still reduced by the currently installed
exact reducer over its complete canonically ordered owner fibre.
"""

from __future__ import annotations

from collections import defaultdict
from heapq import heappop, heappush
from time import monotonic_ns
from typing import Any

import src.pnf.factor_proposals as factor_proposals


_INSTALL_MARKER = "_dependency_indexed_owner_execution_installed"
_SENTINEL_NO_DEPENDENCY = "__sensiblaw:no-known-dependency__"
_SENTINEL_NO_OBSERVATION = "__sensiblaw:no-known-observation__"


def _ensure_dependency_index(owner: Any) -> None:
    if hasattr(owner, "_owners_by_dependency_ref"):
        return

    owner._owners_by_dependency_ref = defaultdict(set)
    owner._owners_by_observation_ref = defaultdict(set)
    owner._dependency_refs_by_owner = defaultdict(set)
    owner._observation_refs_by_owner = defaultdict(set)
    owner._factor_producers_by_ref = defaultdict(set)

    for key, proposals in owner._proposals_by_owner.items():
        for proposal in proposals.values():
            dependencies = tuple(proposal.dependency_factor_refs)
            observations = tuple(proposal.input_observation_refs)
            owner._dependency_refs_by_owner[key].update(dependencies)
            owner._observation_refs_by_owner[key].update(observations)
            for dependency_ref in dependencies:
                owner._owners_by_dependency_ref[dependency_ref].add(key)
            for observation_ref in observations:
                owner._owners_by_observation_ref[observation_ref].add(key)

    for key, reduction in owner._reductions.items():
        for factor in reduction.factors:
            owner._factor_producers_by_ref[factor.factor_ref].add(key)

    # The bounded owner's dependency authority is precisely its currently
    # materialized reduced factors. Reconstruct it from producer multiplicity so
    # one owner cannot remove a dependency ref still produced by another owner.
    owner._known_dependency_refs.clear()
    owner._known_dependency_refs.update(owner._factor_producers_by_ref)


def _strict_dependency_refs(owner: Any) -> set[str]:
    """Interpret an empty bounded-owner dependency set as exactly empty."""

    if owner._known_dependency_refs:
        return owner._known_dependency_refs
    return {_SENTINEL_NO_DEPENDENCY}


def _strict_observation_refs(owner: Any) -> set[str]:
    """Interpret an empty bounded-owner observation set as exactly empty."""

    if owner._observation_refs:
        return owner._observation_refs
    return {_SENTINEL_NO_OBSERVATION}


def _update_factor_availability(
    owner: Any,
    *,
    key: Any,
    before_factors: set[str],
    after_factors: set[str],
) -> set[str]:
    """Update producer multiplicity and return refs whose availability flipped."""

    availability_delta: set[str] = set()

    for factor_ref in before_factors - after_factors:
        producers = owner._factor_producers_by_ref.get(factor_ref)
        if producers is None:
            continue
        producers.discard(key)
        if not producers:
            owner._factor_producers_by_ref.pop(factor_ref, None)
            owner._known_dependency_refs.discard(factor_ref)
            availability_delta.add(factor_ref)

    for factor_ref in after_factors - before_factors:
        producers = owner._factor_producers_by_ref[factor_ref]
        was_available = bool(producers)
        producers.add(key)
        owner._known_dependency_refs.add(factor_ref)
        if not was_available:
            availability_delta.add(factor_ref)

    return availability_delta


def install_dependency_indexed_owner_execution() -> bool:
    from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner

    if getattr(BoundedStreamingSemanticOwner, _INSTALL_MARKER, False):
        return False

    original_index = BoundedStreamingSemanticOwner._index_proposal
    original_admit_observation_delta = BoundedStreamingSemanticOwner.admit_observation_delta

    def index_proposal(self: Any, proposal: Any, *, stage: str):
        indexed = original_index(self, proposal, stage=stage)
        if indexed is None:
            return None
        proposal_ref, key = indexed
        _ensure_dependency_index(self)
        dependencies = tuple(proposal.dependency_factor_refs)
        observations = tuple(proposal.input_observation_refs)
        self._dependency_refs_by_owner[key].update(dependencies)
        self._observation_refs_by_owner[key].update(observations)
        for dependency_ref in dependencies:
            self._owners_by_dependency_ref[dependency_ref].add(key)
        for observation_ref in observations:
            self._owners_by_observation_ref[observation_ref].add(key)
        self._kernel_counts["dependency_reverse_edges_indexed"] += len(dependencies)
        self._kernel_counts["observation_reverse_edges_indexed"] += len(observations)
        return proposal_ref, key

    def admit_observation_delta(self: Any, delta: Any):
        _ensure_dependency_index(self)
        new_refs = set(delta.observation_refs) - self._observation_refs
        if new_refs:
            woken: set[Any] = set()
            for observation_ref in new_refs:
                woken.update(self._owners_by_observation_ref.get(observation_ref, ()))
            self._dirty_groups.update(woken)
            self._kernel_counts["observation_indexed_owner_wakeups"] += len(woken)
        # Dirtying is part of the same canonical revision transition that admits
        # the observations; duplicate/replayed refs produce no wake-up.
        return original_admit_observation_delta(self, delta)

    def reduce_dirty_groups(self: Any):
        """Reduce dirty owners and wake exactly their factor successors."""

        prior = self.revision
        if self._dirty_groups:
            self._materialized_reduction_cache = None
        _ensure_dependency_index(self)

        changed_factors: set[str] = set()
        introduced: set[str] = set()
        discharged: set[str] = set()

        pending: list[Any] = []
        scheduled: set[Any] = set()
        for key in sorted(self._dirty_groups):
            heappush(pending, key)
            scheduled.add(key)
        self._dirty_groups.clear()

        self._kernel_counts["reduction_calls"] += 1
        initial_dirty_count = len(scheduled)
        dependency_wakeups = 0
        dependency_steps = 0

        while pending:
            dependency_steps += 1
            key = heappop(pending)
            scheduled.discard(key)
            owner_proposals = self._proposals_by_owner[key]
            group = tuple(
                owner_proposals[proposal_ref]
                for proposal_ref in sorted(owner_proposals)
            )
            self._kernel_counts["reduction_proposals_scanned"] += len(group)
            self._kernel_counts["max_reduction_fibre_size"] = max(
                self._kernel_counts["max_reduction_fibre_size"], len(group)
            )

            before = self._reductions.get(key)
            reduction_started = monotonic_ns()
            reduction = factor_proposals.reduce_factor_proposals(
                document_ref=self.document_ref,
                proposals=group,
                known_observation_refs=_strict_observation_refs(self),
                known_dependency_refs=_strict_dependency_refs(self),
            )
            self._kernel_elapsed_ns["owner_reduction_ns"] += (
                monotonic_ns() - reduction_started
            )
            self._kernel_counts["reduction_candidate_comparisons"] += int(
                reduction.metrics.get("candidate_comparisons") or 0
            )
            self._reductions[key] = reduction
            self._kernel_counts["dirty_owner_groups_reduced"] += 1

            before_factors = (
                {row.factor_ref for row in before.factors} if before else set()
            )
            after_factors = {row.factor_ref for row in reduction.factors}
            factor_delta = before_factors.symmetric_difference(after_factors)
            availability_delta = _update_factor_availability(
                self,
                key=key,
                before_factors=before_factors,
                after_factors=after_factors,
            )
            changed_factors.update(factor_delta)

            before_residuals = (
                {row.residual_ref for row in before.residuals} if before else set()
            )
            after_residuals = {row.residual_ref for row in reduction.residuals}
            introduced.update(after_residuals - before_residuals)
            discharged.update(before_residuals - after_residuals)

            if availability_delta:
                successors: set[Any] = set()
                for factor_ref in availability_delta:
                    successors.update(self._owners_by_dependency_ref.get(factor_ref, ()))
                for successor in sorted(successors):
                    if successor not in scheduled:
                        heappush(pending, successor)
                        scheduled.add(successor)
                        dependency_wakeups += 1

        self._kernel_counts["initial_dirty_owner_groups"] += initial_dirty_count
        self._kernel_counts["dependency_indexed_owner_wakeups"] += dependency_wakeups
        self._kernel_counts["dependency_reduction_steps"] += dependency_steps
        return self._advance(
            prior_revision=prior,
            changed_factors=changed_factors,
            introduced_residuals=introduced,
            discharged_residuals=discharged,
        )

    BoundedStreamingSemanticOwner._index_proposal = index_proposal
    BoundedStreamingSemanticOwner.admit_observation_delta = admit_observation_delta
    BoundedStreamingSemanticOwner.reduce_dirty_groups = reduce_dirty_groups
    setattr(BoundedStreamingSemanticOwner, _INSTALL_MARKER, True)
    return True


__all__ = ["install_dependency_indexed_owner_execution"]
