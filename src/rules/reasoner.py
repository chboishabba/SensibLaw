"""Simple reasoning over rules."""

import re
from typing import Iterable, List

from . import Rule


NEGATIVE = {"must not", "may not", "shall not"}


def _polarity(modality: str) -> str:
    """Classify a modality as either ``negative`` or ``positive``."""

    return "negative" if modality.lower() in NEGATIVE else "positive"


def check_rules(rules: Iterable[Rule]) -> List[str]:
    """Check a set of rules for contradictions or delegation breaches."""

    issues: List[str] = []
    seen: dict[tuple[str, str], tuple[str, Rule]] = {}

    for rule in rules:
        key = (rule.actor.lower(), rule.action.lower())
        pol = _polarity(rule.modality)
        if key in seen:
            other_pol, other_rule = seen[key]
            if pol != other_pol:
                issues.append(
                    "Contradiction between "
                    f"'{other_rule.actor} {other_rule.modality} {other_rule.action}' and "
                    f"'{rule.actor} {rule.modality} {rule.action}'"
                )
        else:
            seen[key] = (pol, rule)

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
                if _polarity(rule.modality) == "negative":
                    issues.append(
                        f"Delegation breach: {delegate} prohibited from {action}"
                    )
    return issues

