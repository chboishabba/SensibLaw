"""Rule checker applying declarative rule definitions to events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.interfaces.rule_checker import CheckResult


_RULE_DIR = Path(__file__).resolve().parents[2] / "data" / "rules"


def _load_rules() -> List[Dict[str, Any]]:
    """Load rule definitions from :mod:`data/rules`.

    Each JSON file may contain a single rule object or a list of rules.
    A rule is expected to be a mapping with at least an ``id`` and a ``when``
    dictionary specifying key/value pairs that must match on the event for the
    rule to be considered broken.
    """

    rules: List[Dict[str, Any]] = []
    if not _RULE_DIR.exists():
        return rules
    for path in sorted(_RULE_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            rules.extend(data)
        else:
            rules.append(data)
    return rules


_RULES_CACHE: List[Dict[str, Any]] | None = None


def _rules() -> List[Dict[str, Any]]:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        _RULES_CACHE = _load_rules()
    return _RULES_CACHE


def check_event(event: Dict[str, Any]) -> CheckResult:
    """Check *event* against the loaded rules.

    Parameters
    ----------
    event:
        Mapping describing the occurrence being evaluated.

    Returns
    -------
    CheckResult
        A dictionary describing whether a breach occurred, which rules were
        broken and associated details.
    """

    broken: List[str] = []
    details: List[str] = []

    for rule in _rules():
        when: Dict[str, Any] = rule.get("when", {})
        if all(event.get(k) == v for k, v in when.items()):
            broken.append(rule.get("id", "unknown"))
            details.append(rule.get("details", ""))

    return {
        "breach": bool(broken),
        "rules_broken": broken,
        "details": details,
    }
