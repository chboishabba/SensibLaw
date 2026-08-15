"""Numeric-after-spaCy execution constitution.

Text, regex and JSON are boundary capabilities, not ambient semantic-execution
permissions.  This module provides small runtime guards so a defended boundary
is explicit in code review instead of being inferred from a convenient import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable


NUMERIC_HOT_PATH_CONSTITUTION_REF = "sensiblaw.numeric-hot-path.v0_1"


class BoundaryKind(StrEnum):
    INGESTION = "ingestion"
    SPACY_ADAPTER = "spacy_adapter"
    EXTERNAL_PROTOCOL = "external_protocol"
    EXPORT_AUDIT = "export_audit"
    LEGACY_IDENTITY = "legacy_identity"


class BoundaryOperation(StrEnum):
    TEXT = "text"
    REGEX = "regex"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class BoundaryPermit:
    permit_ref: str
    kind: BoundaryKind
    operations: frozenset[BoundaryOperation]
    reason: str

    def require(self, operation: BoundaryOperation) -> None:
        if operation not in self.operations:
            raise RuntimeError(
                f"{self.permit_ref} does not permit {operation.value}; "
                "ordinary semantic execution must remain numeric"
            )


LEGACY_MANIFEST_IDENTITY_BOUNDARY = BoundaryPermit(
    permit_ref="boundary:legacy-manifest-canonical-json:v0_1",
    kind=BoundaryKind.LEGACY_IDENTITY,
    operations=frozenset({BoundaryOperation.JSON}),
    reason=(
        "preserve the existing canonical manifest digest contract while the "
        "normal production carrier migrates away from JSON"
    ),
)


def require_numeric_identifier(value: Any, field: str = "identifier") -> int:
    """Return one semantic numeric identifier or fail closed.

    ``bool`` is rejected even though it is an ``int`` subclass: semantic ids are
    coordinates, not truth values.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer semantic coordinate")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def require_numeric_identifiers(
    values: Iterable[Any], field: str = "identifiers"
) -> tuple[int, ...]:
    return tuple(require_numeric_identifier(value, field) for value in values)


def require_boundary_operation(
    permit: BoundaryPermit,
    operation: BoundaryOperation,
) -> None:
    """Make a nonnumeric boundary operation explicit at the call site."""

    permit.require(operation)


__all__ = [
    "BoundaryKind",
    "BoundaryOperation",
    "BoundaryPermit",
    "LEGACY_MANIFEST_IDENTITY_BOUNDARY",
    "NUMERIC_HOT_PATH_CONSTITUTION_REF",
    "require_boundary_operation",
    "require_numeric_identifier",
    "require_numeric_identifiers",
]
