from __future__ import annotations

import pytest

from src.runtime.numeric_hot_path_constitution import (
    BoundaryKind,
    BoundaryOperation,
    BoundaryPermit,
    LEGACY_MANIFEST_IDENTITY_BOUNDARY,
    require_boundary_operation,
    require_numeric_identifier,
    require_numeric_identifiers,
)


def test_semantic_identifier_requires_nonnegative_int() -> None:
    assert require_numeric_identifier(0) == 0
    assert require_numeric_identifier(42) == 42
    with pytest.raises(TypeError):
        require_numeric_identifier("42")
    with pytest.raises(TypeError):
        require_numeric_identifier(True)
    with pytest.raises(ValueError):
        require_numeric_identifier(-1)


def test_numeric_sequence_fails_on_text_coordinate() -> None:
    assert require_numeric_identifiers((1, 2, 3)) == (1, 2, 3)
    with pytest.raises(TypeError):
        require_numeric_identifiers((1, "two", 3))


def test_legacy_manifest_boundary_permits_only_json() -> None:
    require_boundary_operation(
        LEGACY_MANIFEST_IDENTITY_BOUNDARY,
        BoundaryOperation.JSON,
    )
    with pytest.raises(RuntimeError):
        require_boundary_operation(
            LEGACY_MANIFEST_IDENTITY_BOUNDARY,
            BoundaryOperation.REGEX,
        )
    with pytest.raises(RuntimeError):
        require_boundary_operation(
            LEGACY_MANIFEST_IDENTITY_BOUNDARY,
            BoundaryOperation.TEXT,
        )


def test_boundary_permission_is_explicit_not_ambient() -> None:
    permit = BoundaryPermit(
        permit_ref="boundary:test",
        kind=BoundaryKind.EXTERNAL_PROTOCOL,
        operations=frozenset({BoundaryOperation.TEXT}),
        reason="test external protocol",
    )
    require_boundary_operation(permit, BoundaryOperation.TEXT)
    with pytest.raises(RuntimeError):
        require_boundary_operation(permit, BoundaryOperation.JSON)
