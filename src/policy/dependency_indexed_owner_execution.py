"""Sparse dependency-indexed invalidation for bounded semantic-owner reduction.

The canonical proposal reducer remains authoritative.  This execution strategy
changes only *which* owner fibres are revisited when the set of available
factor dependencies changes.  Proposal admission records an exact reverse
index

    dependency factor ref -> owner keys whose proposals require it

and reduction then follows only those edges to a local fixed point.  No
whole-owner scan is used to discover dependent fibres.

The wrapper deliberately does not assume same-owner reduction is associative or
append-homomorphic.  Each woken owner is still reduced by the canonical reducer
over its complete canonically ordered owner fibre.
"""

from __future__ import annotations

from collections import defaultdict
from heapq import heappop, heappush
from time import monotonic_ns
from typing import Any

from src.pnf.factor_proposals import reduce_factor_proposals


_INSTALL_MARKER = "_dependency_indexed_owner_execution_installed"
_SENTINEL_NO_DEPENDENCY = "__sensiblaw:no-known-dependency__"


def _ensure_dependency_index(owner: Any) -> None:
    if hasattr(owner, "_owners_by_dependency_ref"):
        return
    owner._owners_by_dependency_ref = defaultdict(set)
    owner._dependency_refs_by_owner = defaultdict(set)
    for key, proposals in owner._proposals_by_owner.items():
        for proposal in proposals.values():
            dependencies = tuple(proposal.dependency_factor_refs)
            owner._dependency_refs_by_owner[key].update(dependencies)
            for dependency_ref in dependencies:
                owner._owners_by_dependency_ref[dependency_ref].add(key)


def _strict_dependency_refs(owner: Any) -> set[str]:
    """Tell the generic reducer that an empty known set is still authoritative.

    ``reduce_factor_proposals`` treats a falsey known-dependency collection as
    "dependency validation not requested" for compatibility callers.  The
    bounded owner *does* own a live dependency-availability set, so an empty set
    means no dependency factor is currently available.  A private impossible
    sentinel keeps that distinction without changing the generic reducer API.
    """

    if owner._known_dependency_refs:
        return owner._known_dependency_refs
    return {_SENTINEL_NO_DEPENDENCY}


def install_dependency_indexed_owner_execution() -> bool:
    from src.pnf.bounded_streaming_owner import BoundedStreamingSemanticOwner

    if getattr(BoundedStreamingSemanticOwner, _INSTALL_MARKER, False):
        return False

    original_index = BoundedStreamingSemanticOwner._index_proposal

    def index_proposal(self: Any, proposal: Any, *, stage: str):
        indexed = original_index(self, proposal, stage=stage)
        if indexed is None:
            return None
        proposal_ref, key = indexed
        _ensure_dependency_index(self)
        dependencies = tuple(proposal.dependency_factor_refs)
        self._dependency_refs_by_owner[key].update(dependencies)
        for dependency_ref in dependencies:
            self._owners_by_dependency_ref[dependency_ref].add(key)
        self._kernel_counts["dependency_reverse_edges_indexed"] += len(dependencies)
        return proposal_ref, key

    def reduce_dirty_groups(self: Any):
        """Reduce dirty owners and wake exactly their dependency successors."""

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
        dependency_rounds = 0

        while pending:
            dependency_rounds += 1
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
            reduction = reduce_factor_proposals(
                document_ref=self.document_ref,
                proposals=group,
                known_observation_refs=self._observation_refs,
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

            self._known_dependency_refs.difference_update(before_factors - after_factors)
            self._known_dependency_refs.update(after_factors)
            changed_factors.update(factor_delta)

            before_residuals = (
                {row.residual_ref for row in before.residuals} if before else set()
            )
            after_residuals = {row.residual_ref for row in reduction.residuals}
            introduced.update(after_residuals - before_residuals)
            discharged.update(before_residuals - after_residuals)

            if factor_delta:
                successors: set[Any] = set()
                for factor_ref in factor_delta:
                    successors.update(self._owners_by_dependency_ref.get(factor_ref, ()))
                for successor in sorted(successors):
                    if successor not in scheduled:
                        heappush(pending, successor)
                        scheduled.add(successor)
                        dependency_wakeups += 1

        self._kernel_counts["initial_dirty_owner_groups"] += initial_dirty_count
        self._kernel_counts["dependency_indexed_owner_wakeups"] += dependency_wakeups
        self._kernel_counts["dependency_reduction_steps"] += dependency_rounds
        return self._advance(
            prior_revision=prior,
            changed_factors=changed_factors,
            introduced_residuals=introduced,
            discharged_residuals=discharged,
        )

    BoundedStreamingSemanticOwner._index_proposal = index_proposal
    BoundedStreamingSemanticOwner.reduce_dirty_groups = reduce_dirty_groups
    setattr(BoundedStreamingSemanticOwner, _INSTALL_MARKER, True)
    return True


__all__ = ["install_dependency_indexed_owner_execution"]
