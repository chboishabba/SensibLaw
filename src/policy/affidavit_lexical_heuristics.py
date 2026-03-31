"""Shared affidavit lexical heuristic helpers."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any


LEXICAL_HEURISTIC_HINT_RULES: dict[str, tuple[dict[str, Any], ...]] = {
    "justification": (
        {
            "rule_id": "justification.consent",
            "label": "consent",
            "patterns": (
                r"\bconsent\b",
                r"\bwith consent\b",
                r"\bknowledge and consent\b",
                r"\bpermission\b",
            ),
        },
        {
            "rule_id": "justification.authority_or_necessity",
            "label": "authority_or_necessity",
            "patterns": (
                r"\bepoa\b",
                r"\bduty\b",
                r"\bduties\b",
                r"\bauthority\b",
                r"\blegal matters\b",
                r"\bcare\b",
            ),
        },
        {
            "rule_id": "justification.scope_limitation",
            "label": "scope_limitation",
            "patterns": (
                r"\bspecific purposes\b",
                r"\bonly to\b",
                r"\blimited\b",
                r"\bminimally\b",
                r"\bno further than necessary\b",
            ),
        },
    ),
}


@lru_cache(maxsize=32768)
def apply_lexical_heuristic_group(text: str, group: str) -> dict[str, list[dict[str, Any]]]:
    matches: dict[str, list[dict[str, Any]]] = {}
    for rule in LEXICAL_HEURISTIC_HINT_RULES.get(group, ()):
        label = str(rule.get("label") or "").strip()
        rule_id = str(rule.get("rule_id") or "").strip()
        if not label or not rule_id:
            continue
        rule_matches: list[dict[str, Any]] = []
        for pattern in rule.get("patterns", ()):
            compiled = re.compile(str(pattern), re.IGNORECASE)
            for match in compiled.finditer(text):
                rule_matches.append(
                    {
                        "rule_id": rule_id,
                        "text": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        if rule_matches:
            matches[label] = rule_matches
    return matches


def build_justification_packets(excerpt_text: str) -> list[dict[str, Any]]:
    excerpt = str(excerpt_text or "")
    packets: list[dict[str, Any]] = []
    rule_matches = apply_lexical_heuristic_group(excerpt, "justification")
    for justification_type, matches in rule_matches.items():
        if not matches:
            continue
        match = matches[0]
        packets.append(
            {
                "type": justification_type,
                "rule_id": match["rule_id"],
                "span": {
                    "text": match["text"],
                    "start": match["start"],
                    "end": match["end"],
                },
                "target_component": "predicate_text",
                "bound_response_span": {
                    "text": match["text"],
                    "start": match["start"],
                    "end": match["end"],
                },
            }
        )
    return packets


__all__ = [
    "LEXICAL_HEURISTIC_HINT_RULES",
    "apply_lexical_heuristic_group",
    "build_justification_packets",
]
