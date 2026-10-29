"""Generic desired/current keyed-relation reconciliation.

This module owns the reusable execution contract shared by SQL-backed and
in-memory reducers. It deliberately separates semantic identity (the key),
mutable execution payload, and physical write count.

Golden formal owners live in dashi_agda:
- DASHI.Cognition.PNF.SetwiseGroupedFibreProjectionExact.DeltaFedProjection
- DASHI.Cognition.PNF.AffectedBoundaryLocalReductionExact.AffectedLocalReducer

The Python carrier is an execution instance. It does not create semantic or
proof authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, Mapping, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True, slots=True)
class RelationDeltaOwnerRouting:
    """Executable single-owner contract for one keyed relation."""

    candidate_mutation_owner_count: int
    private_candidate_mutation_bypass_count: int
    hot_path_reconciler_owner_count: int
    reconciliation_receipt_owner_count: int

    def __post_init__(self) -> None:
        if self.candidate_mutation_owner_count != 1:
            raise ValueError("candidate relation must have exactly one mutation owner")
        if self.private_candidate_mutation_bypass_count != 0:
            raise ValueError("private candidate mutation bypasses are forbidden")
        if self.hot_path_reconciler_owner_count != 1:
            raise ValueError("hot path must have exactly one reconciler owner")
        if self.reconciliation_receipt_owner_count != self.hot_path_reconciler_owner_count:
            raise ValueError("reconciliation receipt owner must match the hot-path owner")

    def receipt(self, *, owner_ref: str) -> dict[str, object]:
        return {
            "contract_ref": "sensiblaw.relation-delta-owner-routing.v0_1",
            "owner_ref": str(owner_ref),
            "candidate_mutation_owner_count": self.candidate_mutation_owner_count,
            "private_candidate_mutation_bypass_count": self.private_candidate_mutation_bypass_count,
            "hot_path_reconciler_owner_count": self.hot_path_reconciler_owner_count,
            "reconciliation_receipt_owner_count": self.reconciliation_receipt_owner_count,
            "semantic_authority_effect": "none",
        }


CANONICAL_CANDIDATE_RELATION_OWNER_ROUTING = RelationDeltaOwnerRouting(
    candidate_mutation_owner_count=1,
    private_candidate_mutation_bypass_count=0,
    hot_path_reconciler_owner_count=1,
    reconciliation_receipt_owner_count=1,
)


@dataclass(frozen=True, slots=True)
class RelationDelta(Generic[K, V]):
    added: Mapping[K, V]
    removed: Mapping[K, V]
    replaced: Mapping[K, tuple[V, V]]
    unchanged: Mapping[K, V]

    @property
    def desired_count(self) -> int:
        return len(self.added) + len(self.replaced) + len(self.unchanged)

    @property
    def current_count(self) -> int:
        return len(self.removed) + len(self.replaced) + len(self.unchanged)

    @property
    def physical_row_mutations(self) -> int:
        # A replacement is intentionally represented as delete+insert unless a
        # domain proves that an in-place update has identical transition meaning.
        return len(self.added) + len(self.removed) + 2 * len(self.replaced)

    @property
    def unchanged_rows_skipped(self) -> int:
        return len(self.unchanged)

    @property
    def changed_key_count(self) -> int:
        return len(self.added) + len(self.removed) + len(self.replaced)

    @property
    def affected_keys(self) -> frozenset[K]:
        """Keys whose authoritative relation value changed."""

        return frozenset(self.added) | frozenset(self.removed) | frozenset(self.replaced)

    @property
    def is_noop(self) -> bool:
        return self.changed_key_count == 0

    def receipt(self, *, owner_ref: str) -> dict[str, object]:
        return {
            "contract_ref": "sensiblaw.relation-delta.v0_1",
            "owner_ref": str(owner_ref),
            "desired_rows": self.desired_count,
            "current_rows": self.current_count,
            "added_rows": len(self.added),
            "removed_rows": len(self.removed),
            "replaced_rows": len(self.replaced),
            "unchanged_rows_skipped": self.unchanged_rows_skipped,
            "changed_key_count": self.changed_key_count,
            "affected_key_count": len(self.affected_keys),
            "physical_row_mutations": self.physical_row_mutations,
            "semantic_authority_effect": "owner-defined",
            "unchanged_rows_emit_transitions": False,
        }


def relation_delta(
    current: Mapping[K, V] | Iterable[tuple[K, V]],
    desired: Mapping[K, V] | Iterable[tuple[K, V]],
) -> RelationDelta[K, V]:
    """Partition two keyed relations into add/remove/replace/unchanged fibres."""

    current_map = dict(current)
    desired_map = dict(desired)

    current_keys = current_map.keys()
    desired_keys = desired_map.keys()

    added = {key: desired_map[key] for key in desired_keys - current_keys}
    removed = {key: current_map[key] for key in current_keys - desired_keys}

    replaced: dict[K, tuple[V, V]] = {}
    unchanged: dict[K, V] = {}
    for key in current_keys & desired_keys:
        old = current_map[key]
        new = desired_map[key]
        if old == new:
            unchanged[key] = old
        else:
            replaced[key] = (old, new)

    return RelationDelta(
        added=added,
        removed=removed,
        replaced=replaced,
        unchanged=unchanged,
    )


__all__ = [
    "CANONICAL_CANDIDATE_RELATION_OWNER_ROUTING",
    "RelationDelta",
    "RelationDeltaOwnerRouting",
    "relation_delta",
]
