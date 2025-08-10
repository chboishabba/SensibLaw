"""Rule extraction utilities."""

import re
from typing import List

from . import Rule

_PATTERN = re.compile(
    r"(?P<actor>.+?)\s+(?P<modality>must not|may not|must|shall|may)\s+(?P<rest>.+)",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[.;]\s*", text)
    return [p.strip() for p in parts if p.strip()]


def extract_rules(text: str) -> List[Rule]:
    """Extract rules from a provision text using regex heuristics."""

    rules: List[Rule] = []
    for sent in _split_sentences(text):
        m = _PATTERN.match(sent)
        if not m:
            continue
        actor = m.group("actor").strip()
        modality = m.group("modality").lower()
        rest = m.group("rest").strip()

        conditions = None
        scope = None
        action = rest

        cond_match = re.search(r"\b(if|when|unless)\b(.*)", rest, re.IGNORECASE)
        if cond_match:
            action = rest[: cond_match.start()].strip()
            conditions = cond_match.group(0).strip()

        scope_match = re.search(r"\b(within|under)\b(.*)", action, re.IGNORECASE)
        if scope_match:
            scope = scope_match.group(0).strip()
            action = action[: scope_match.start()].strip()

        rules.append(
            Rule(
                actor=actor,
                modality=modality,
                action=action,
                conditions=conditions,
                scope=scope,
            )
        )
    return rules

