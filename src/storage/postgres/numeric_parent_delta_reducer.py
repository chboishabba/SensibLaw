"""Delta-native parent frontier planning over transported boundary carriers.

The semantic authority remains PostgreSQL.  This module owns the typed runtime
bridge between the DASHI affected-key work model and the canonical database
reducer introduced by migration 202.

Two rules are deliberately enforced here:

* closed child interiors are not read; only transported child boundary atoms and
  transported actor/action summaries may feed a parent;
* a work receipt distinguishes accumulated parent boundary size from the keys
  actually reconsidered.  The latter is the structural quantity that should
  scale with emitted deltas and hierarchy depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Iterable, Mapping

from src.pnf.numeric_hyperfabric import TargetKind, numeric_digest


DEFAULT_PARENT_KEY_BUDGET = 8192


class BoundaryKeyFamily(IntEnum):
    OBJECT = 1
    FACTOR = 2
    DEMAND = 3
    ACTOR = 4
    OUTWARD = 5


@dataclass(frozen=True, slots=True)
class ParentBoundaryAtom:
    child_region_id: int
    child_interface_id: int
    export_kind: int
    target_kind: int
    target_id: int
    key_symbol_id: int | None
    role_symbol_id: int | None
    residual_type_symbol_id: int | None
    rank: int
    promotion_score: float
    scope_class: int
    origin_interface_id: int | None
    outward_required: bool


@dataclass(frozen=True, slots=True)
class ParentActorAtom:
    child_region_id: int
    child_interface_id: int
    object_id: int
    object_kind_symbol_id: int | None
    role_symbol_id: int | None
    factor_type_symbol_id: int | None
    predicate_symbol_id: int | None
    occurrence_count: int
    first_start_char: int
    last_end_char: int
    promotion_score: float


@dataclass(frozen=True, slots=True, order=True)
class AffectedParentKey:
    family: BoundaryKeyFamily
    key_a: int
    key_b: int = 0
    key_c: int = 0


@dataclass(frozen=True, slots=True)
class ParentDeltaWorkPlan:
    parent_region_id: int
    accumulated_boundary_atoms: int
    accumulated_boundary_keys: int
    affected_keys: tuple[AffectedParentKey, ...]
    object_keys: int
    factor_keys: int
    demand_keys: int
    actor_keys: int
    outward_keys: int
    hierarchy_depth: int
    emitted_parent_deltas: int = 0

    @property
    def touched_key_count(self) -> int:
        return len(self.affected_keys)

    @property
    def hierarchy_transport_work(self) -> int:
        return self.emitted_parent_deltas * self.hierarchy_depth


@dataclass(frozen=True, slots=True)
class ParentDeltaReductionReceipt:
    interface_id: int
    parent_region_id: int
    input_delta_atoms: int
    accumulated_boundary_keys: int
    touched_boundary_keys: int
    object_keys_touched: int
    factor_keys_touched: int
    demand_keys_touched: int
    actor_keys_touched: int
    outward_keys_touched: int
    emitted_parent_deltas: int
    hierarchy_depth: int
    cold_build: bool
    output_export_count: int
    unresolved_demand_count: int
    resolved_demand_count: int
    actor_profile_count: int
    elapsed_ms: float

    @property
    def hierarchy_transport_work(self) -> int:
        return self.emitted_parent_deltas * self.hierarchy_depth


def _boundary_key(atom: ParentBoundaryAtom) -> AffectedParentKey:
    target_kind = int(atom.target_kind)
    if target_kind == int(TargetKind.OBJECT):
        return AffectedParentKey(BoundaryKeyFamily.OBJECT, atom.target_id)
    if target_kind == int(TargetKind.FACTOR):
        return AffectedParentKey(BoundaryKeyFamily.FACTOR, atom.target_id)
    if target_kind == int(TargetKind.DEMAND):
        return AffectedParentKey(BoundaryKeyFamily.DEMAND, atom.target_id)
    return AffectedParentKey(
        BoundaryKeyFamily.OUTWARD,
        atom.export_kind,
        atom.target_kind,
        atom.target_id,
    )


def _actor_key(atom: ParentActorAtom) -> AffectedParentKey:
    return AffectedParentKey(
        BoundaryKeyFamily.ACTOR,
        atom.object_id,
        atom.role_symbol_id or 0,
        atom.factor_type_symbol_id or 0,
    )


def boundary_fingerprints(
    boundary_atoms: Iterable[ParentBoundaryAtom],
    actor_atoms: Iterable[ParentActorAtom],
) -> dict[AffectedParentKey, bytes]:
    """Return deterministic fingerprints for each parent-local boundary fibre."""

    grouped: dict[AffectedParentKey, list[tuple[object, ...]]] = {}
    for atom in boundary_atoms:
        key = _boundary_key(atom)
        grouped.setdefault(key, []).append(
            (
                atom.child_region_id,
                atom.child_interface_id,
                atom.export_kind,
                atom.target_kind,
                atom.target_id,
                atom.key_symbol_id or 0,
                atom.role_symbol_id or 0,
                atom.residual_type_symbol_id or 0,
                atom.rank,
                atom.promotion_score,
                atom.scope_class,
                atom.origin_interface_id or 0,
                atom.outward_required,
            )
        )
    for atom in actor_atoms:
        key = _actor_key(atom)
        grouped.setdefault(key, []).append(
            (
                atom.child_region_id,
                atom.child_interface_id,
                atom.object_id,
                atom.object_kind_symbol_id or 0,
                atom.role_symbol_id or 0,
                atom.factor_type_symbol_id or 0,
                atom.predicate_symbol_id or 0,
                atom.occurrence_count,
                atom.first_start_char,
                atom.last_end_char,
                atom.promotion_score,
            )
        )
    return {
        key: numeric_digest(key.family, key.key_a, key.key_b, key.key_c, *sorted(rows))
        for key, rows in grouped.items()
    }


def affected_keys_from_fingerprints(
    current: Mapping[AffectedParentKey, bytes],
    previous: Mapping[AffectedParentKey, bytes] | None,
) -> tuple[AffectedParentKey, ...]:
    """Return only fibres whose transported child-boundary input changed."""

    if previous is None:
        return tuple(sorted(current))
    keys = set(current) | set(previous)
    return tuple(sorted(key for key in keys if current.get(key) != previous.get(key)))


def _enforce_family_budget(
    keys: Iterable[AffectedParentKey],
    *,
    key_budget: int,
) -> None:
    if key_budget < 1:
        raise ValueError("parent boundary key budget must be positive")
    counts: dict[BoundaryKeyFamily, int] = {family: 0 for family in BoundaryKeyFamily}
    for key in keys:
        counts[key.family] += 1
    oversized = {family: count for family, count in counts.items() if count > key_budget}
    if oversized:
        detail = ", ".join(
            f"{family.name.lower()}={count}" for family, count in sorted(oversized.items())
        )
        raise RuntimeError(
            f"delta-native parent boundary exceeds exact per-family budget "
            f"{key_budget}: {detail}"
        )


def load_parent_boundary_atoms(
    cursor: Any,
    *,
    parent_region_id: int,
) -> tuple[ParentBoundaryAtom, ...]:
    cursor.execute(
        """
        SELECT child_region_id,
               child_interface_id,
               export_kind,
               target_kind,
               target_id,
               key_symbol_id,
               role_symbol_id,
               residual_type_symbol_id,
               rank,
               promotion_score,
               scope_class,
               origin_interface_id,
               outward_required
          FROM execution.semantic_pnf_parent_delta_projection
         WHERE parent_region_id = %s
         ORDER BY child_interface_id,
                  export_kind,
                  target_kind,
                  target_id
        """,
        (parent_region_id,),
    )
    return tuple(
        ParentBoundaryAtom(
            child_region_id=int(row[0]),
            child_interface_id=int(row[1]),
            export_kind=int(row[2]),
            target_kind=int(row[3]),
            target_id=int(row[4]),
            key_symbol_id=int(row[5]) if row[5] is not None else None,
            role_symbol_id=int(row[6]) if row[6] is not None else None,
            residual_type_symbol_id=int(row[7]) if row[7] is not None else None,
            rank=int(row[8]),
            promotion_score=float(row[9]),
            scope_class=int(row[10]),
            origin_interface_id=int(row[11]) if row[11] is not None else None,
            outward_required=bool(row[12]),
        )
        for row in cursor.fetchall()
    )


def load_parent_actor_atoms(
    cursor: Any,
    *,
    parent_region_id: int,
) -> tuple[ParentActorAtom, ...]:
    cursor.execute(
        """
        SELECT child_region_id,
               child_interface_id,
               object_id,
               object_kind_symbol_id,
               role_symbol_id,
               factor_type_symbol_id,
               predicate_symbol_id,
               occurrence_count,
               first_start_char,
               last_end_char,
               promotion_score
          FROM execution.semantic_pnf_parent_actor_delta_projection
         WHERE parent_region_id = %s
         ORDER BY child_interface_id,
                  object_id,
                  role_symbol_id,
                  factor_type_symbol_id,
                  predicate_symbol_id
        """,
        (parent_region_id,),
    )
    return tuple(
        ParentActorAtom(
            child_region_id=int(row[0]),
            child_interface_id=int(row[1]),
            object_id=int(row[2]),
            object_kind_symbol_id=int(row[3]) if row[3] is not None else None,
            role_symbol_id=int(row[4]) if row[4] is not None else None,
            factor_type_symbol_id=int(row[5]) if row[5] is not None else None,
            predicate_symbol_id=int(row[6]) if row[6] is not None else None,
            occurrence_count=int(row[7]),
            first_start_char=int(row[8]),
            last_end_char=int(row[9]),
            promotion_score=float(row[10]),
        )
        for row in cursor.fetchall()
    )


def plan_parent_delta_work(
    cursor: Any,
    *,
    parent_region_id: int,
    hierarchy_depth: int,
    previous_fingerprints: Mapping[AffectedParentKey, bytes] | None = None,
    key_budget: int = DEFAULT_PARENT_KEY_BUDGET,
) -> tuple[ParentDeltaWorkPlan, dict[AffectedParentKey, bytes]]:
    """Plan exact parent-local work without reading any closed child interior."""

    if hierarchy_depth < 0:
        raise ValueError("hierarchy depth must be non-negative")
    boundary_atoms = load_parent_boundary_atoms(cursor, parent_region_id=parent_region_id)
    actor_atoms = load_parent_actor_atoms(cursor, parent_region_id=parent_region_id)
    current = boundary_fingerprints(boundary_atoms, actor_atoms)
    _enforce_family_budget(current, key_budget=key_budget)
    affected = affected_keys_from_fingerprints(current, previous_fingerprints)
    counts = {family: 0 for family in BoundaryKeyFamily}
    for key in affected:
        counts[key.family] += 1
    return (
        ParentDeltaWorkPlan(
            parent_region_id=parent_region_id,
            accumulated_boundary_atoms=len(boundary_atoms) + len(actor_atoms),
            accumulated_boundary_keys=len(current),
            affected_keys=affected,
            object_keys=counts[BoundaryKeyFamily.OBJECT],
            factor_keys=counts[BoundaryKeyFamily.FACTOR],
            demand_keys=counts[BoundaryKeyFamily.DEMAND],
            actor_keys=counts[BoundaryKeyFamily.ACTOR],
            outward_keys=counts[BoundaryKeyFamily.OUTWARD],
            hierarchy_depth=hierarchy_depth,
        ),
        current,
    )


def reduce_parent_frontier_from_delta(
    cursor: Any,
    *,
    interface_id: int,
    hierarchy_depth: int,
    key_budget: int = DEFAULT_PARENT_KEY_BUDGET,
) -> ParentDeltaReductionReceipt:
    """Run the migration-202 canonical reducer and return its structural receipt."""

    cursor.execute(
        "SELECT * FROM execution.reduce_numeric_pnf_parent_frontier_delta_native(%s, %s, %s)",
        (interface_id, hierarchy_depth, key_budget),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("delta-native parent reducer returned no receipt")
    return ParentDeltaReductionReceipt(
        interface_id=interface_id,
        parent_region_id=int(row[0]),
        input_delta_atoms=int(row[1]),
        accumulated_boundary_keys=int(row[2]),
        touched_boundary_keys=int(row[3]),
        object_keys_touched=int(row[4]),
        factor_keys_touched=int(row[5]),
        demand_keys_touched=int(row[6]),
        actor_keys_touched=int(row[7]),
        outward_keys_touched=int(row[8]),
        emitted_parent_deltas=int(row[9]),
        hierarchy_depth=int(row[10]),
        cold_build=bool(row[11]),
        output_export_count=int(row[12]),
        unresolved_demand_count=int(row[13]),
        resolved_demand_count=int(row[14]),
        actor_profile_count=int(row[15]),
        elapsed_ms=float(row[16]),
    )


__all__ = [
    "AffectedParentKey",
    "BoundaryKeyFamily",
    "DEFAULT_PARENT_KEY_BUDGET",
    "ParentActorAtom",
    "ParentBoundaryAtom",
    "ParentDeltaReductionReceipt",
    "ParentDeltaWorkPlan",
    "affected_keys_from_fingerprints",
    "boundary_fingerprints",
    "load_parent_actor_atoms",
    "load_parent_boundary_atoms",
    "plan_parent_delta_work",
    "reduce_parent_frontier_from_delta",
]
