"""Simple reasoning over rules."""

import re
from typing import Iterable, List

from . import Rule


def check_rules(rules: Iterable[Rule]) -> List[str]:
    """Check a set of rules for contradictions or delegation breaches."""

    issues: List[str] = []
    seen: dict[tuple[str, str], Rule] = {}

    for rule in rules:
        key = (rule.actor.lower(), rule.action.lower())
        if key in seen:
            other = seen[key]
            if rule.modality != other.modality:
                issues.append(
                    "Contradiction between "
                    f"'{other.actor} {other.modality} {other.action}' and "
                    f"'{rule.actor} {rule.modality} {rule.action}'"
                )
        else:
            seen[key] = rule

    # Detect delegation breaches
    delegations: list[tuple[str, str]] = []  # (delegate, action)
    for rule in rules:
        m = re.search(
            r"delegate(?:s|d)?\s+(?P<action>.*?)\s+to\s+(?P<delegate>.+)",
            rule.action,
            re.IGNORECASE,
        )
        if m:
            action = m.group("action").strip().lower()
            delegate = m.group("delegate").strip().lower()
            delegations.append((delegate, action))

    for delegate, action in delegations:
        for rule in rules:
            if rule.actor.lower() == delegate and action in rule.action.lower():
                if "must not" in rule.modality:
                    issues.append(
                        f"Delegation breach: {delegate} prohibited from {action}"
                    )
    return issues

