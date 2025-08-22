"""Interface for rule checking events."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class CheckResult(TypedDict):
    """Result of evaluating an event against a set of rules."""

    breach: bool
    rules_broken: List[str]
    details: List[str]


def check_event(event: Dict[str, Any]) -> CheckResult:  # pragma: no cover - interface stub
    """Check an event against the configured rules.

    Parameters
    ----------
    event:
        Mapping describing the occurrence being evaluated.

    Returns
    -------
    CheckResult
        Dictionary with ``breach`` flag, ``rules_broken`` identifiers and
        ``details`` describing the breach.
    """

    raise NotImplementedError
