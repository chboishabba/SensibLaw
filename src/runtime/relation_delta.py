"""Generic desired/current keyed-relation reconciliation.

This module owns the reusable execution contract shared by SQL-backed and
in-memory reducers.  It deliberately separates semantic identity (the key),
mutable execution payload, and physical write count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, Mapping, TypeVar

K = TypeVar("K")
V = TypeVar("V")


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


__all__ = ["RelationDelta", "relation_delta"]
