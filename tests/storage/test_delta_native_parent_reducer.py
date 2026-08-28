from __future__ import annotations

import pytest

from src.storage.postgres.numeric_parent_delta_reducer import (
    AffectedParentKey,
    BoundaryKeyFamily,
    ParentActorAtom,
    ParentBoundaryAtom,
    _enforce_family_budget,
    affected_keys_from_fingerprints,
    boundary_fingerprints,
)


def _object_atom(*, child: int, target: int, promotion: float = 1.0) -> ParentBoundaryAtom:
    return ParentBoundaryAtom(
        child_region_id=child,
        child_interface_id=child + 100,
        export_kind=1,
        target_kind=1,
        target_id=target,
        key_symbol_id=target + 1000,
        role_symbol_id=None,
        residual_type_symbol_id=None,
        rank=0,
        promotion_score=promotion,
        scope_class=3,
        origin_interface_id=child + 100,
        outward_required=False,
    )


def _actor_atom(*, child: int, object_id: int, occurrences: int = 1) -> ParentActorAtom:
    return ParentActorAtom(
        child_region_id=child,
        child_interface_id=child + 100,
        object_id=object_id,
        object_kind_symbol_id=41,
        role_symbol_id=42,
        factor_type_symbol_id=43,
        predicate_symbol_id=44,
        occurrence_count=occurrences,
        first_start_char=10,
        last_end_char=20,
        promotion_score=1.5,
    )


def test_boundary_fingerprints_are_order_independent_and_family_local() -> None:
    first = _object_atom(child=1, target=10)
    second = _object_atom(child=2, target=11)
    actor = _actor_atom(child=1, object_id=10)

    left = boundary_fingerprints((first, second), (actor,))
    right = boundary_fingerprints((second, first), (actor,))

    assert left == right
    assert set(left) == {
        AffectedParentKey(BoundaryKeyFamily.OBJECT, 10),
        AffectedParentKey(BoundaryKeyFamily.OBJECT, 11),
        AffectedParentKey(BoundaryKeyFamily.ACTOR, 10, 42, 43),
    }


def test_changed_fibre_only_marks_its_parent_key() -> None:
    before = boundary_fingerprints(
        (_object_atom(child=1, target=10), _object_atom(child=2, target=11)),
        (),
    )
    after = boundary_fingerprints(
        (
            _object_atom(child=1, target=10, promotion=2.0),
            _object_atom(child=2, target=11),
        ),
        (),
    )

    assert affected_keys_from_fingerprints(after, before) == (
        AffectedParentKey(BoundaryKeyFamily.OBJECT, 10),
    )


def test_removed_fibre_survives_as_affected_tombstone() -> None:
    removed_key = AffectedParentKey(BoundaryKeyFamily.OBJECT, 10)
    before = boundary_fingerprints((_object_atom(child=1, target=10),), ())
    after: dict[AffectedParentKey, bytes] = {}

    assert affected_keys_from_fingerprints(after, before) == (removed_key,)


def test_no_change_has_no_affected_parent_work() -> None:
    state = boundary_fingerprints((_object_atom(child=1, target=10),), ())
    assert affected_keys_from_fingerprints(state, state) == ()


def test_exact_family_budget_fails_closed_instead_of_truncating() -> None:
    keys = (
        AffectedParentKey(BoundaryKeyFamily.OBJECT, 1),
        AffectedParentKey(BoundaryKeyFamily.OBJECT, 2),
    )
    with pytest.raises(RuntimeError, match="object=2"):
        _enforce_family_budget(keys, key_budget=1)
