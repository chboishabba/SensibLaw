"""Rule extraction utilities."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from . import Rule, derive_party_metadata

# Include the most common English legal modalities.  The patterns capture
# normative "must/may" statements as well as offence formulations such as
# "commits murder if".  The offence patterns normalise the modality to include
# the offence label so downstream consumers can still reason about the actor's
# behaviour.
_NORMATIVE_PATTERN = re.compile(
    r"(?P<actor>.+?)\s+(?P<modality>must not|may not|shall not|must|shall|may)\s+(?P<rest>.+)",
    re.IGNORECASE,
)

_OFFENCE_PATTERN = re.compile(
    r"(?P<actor>.+?)\s+(?P<modality>commits(?: the offence of)?|is guilty of)\s+"
    r"(?P<offence>[^,.;]+?)\s+(?P<trigger>if|when|where|by)\s+(?P<rest>.+)",
    re.IGNORECASE,
)

_PATTERNS = [_NORMATIVE_PATTERN, _OFFENCE_PATTERN]

_FAULT_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bintentionally\b",
        r"\bknowingly\b",
        r"\brecklessly\b",
        r"\bnegligently\b",
        r"\bwilfully\b",
        r"\bmaliciously\b",
        r"\bdeliberately\b",
        r"\bwith intent(?:ion)? to\b[^,;]+",
        r"\bwith the intention of\b[^,;]+",
    ]
]

_RESULT_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bresult(?:s|ing)? in\b[^,;]+",
        r"\bso as to\b[^,;]+",
        r"\bso that\b[^,;]+",
        r"\bthereby\s+(?:causing|resulting in)\b[^,;]+",
        r"\bleading to\b[^,;]+",
    ]
]

_EXCEPTION_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bunless\b[^.]+",
        r"\bexcept(?: where| that| as)?\b[^.]+",
    ]
]

_CIRCUMSTANCE_PATTERNS = [
    re.compile(pat, re.IGNORECASE)
    for pat in [
        r"\bin\s+(?:a|an|the)?[^,;.]+",
        r"\bon\s+(?:a|an|the)?[^,;.]+",
        r"\bat\s+(?:a|an|the)?[^,;.]+",
        r"\bwithin\s+[^,;.]+",
        r"\bunder\s+[^,;.]+",
        r"\bwhile\s+[^,;.]+",
        r"\bduring\s+[^,;.]+",
        r"\bwithout\s+[^,;.]+",
        r"\bby\s+[^,;.]+",
        r"\busing\s+[^,;.]+",
        r"\bwith\s+(?!intent(?:ion)?\b)[^,;.]+",
    ]
]


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"[.;]\s*", text)
    sentences: List[str] = []
    for part in parts:
        for line in part.splitlines():
            candidate = line.strip()
            if candidate:
                sentences.append(candidate)
    return sentences


def _clean_fragment(fragment: str) -> str:
    fragment = re.sub(r"\s+", " ", fragment)
    return fragment.strip(" ,.;:")


def _extract_patterns(text: str, patterns: List[re.Pattern[str]]) -> tuple[List[str], str]:
    """Extract ``patterns`` from ``text`` returning matches and remainder."""

    matches: List[str] = []
    remainder = text

    for pattern in patterns:
        if not remainder:
            break

        def _repl(match: re.Match[str]) -> str:
            fragment = _clean_fragment(match.group(0))
            if fragment and fragment.lower() not in {m.lower() for m in matches}:
                matches.append(fragment)
            return " "

        remainder = pattern.sub(_repl, remainder)

    return matches, remainder


def _classify_fragments(action: str, conditions: str | None, scope: str | None) -> Dict[str, List[str]]:
    """Classify clause fragments into offence element roles."""

    roles: Dict[str, List[str]] = defaultdict(list)

    working_action = action or ""

    if working_action:
        leading_cond = re.match(r"\b(if|when|where)\b\s+(?P<body>.+)", working_action, re.IGNORECASE)
        if leading_cond:
            fragment = _clean_fragment(leading_cond.group(0))
            if fragment:
                roles["circumstance"].append(fragment)
            working_action = leading_cond.group("body")

    action_exceptions, working_action = _extract_patterns(working_action, _EXCEPTION_PATTERNS)
    if action_exceptions:
        roles["exception"].extend(action_exceptions)

    faults, working_action = _extract_patterns(working_action, _FAULT_PATTERNS)
    if faults:
        roles["fault"].extend(faults)

    results, working_action = _extract_patterns(working_action, _RESULT_PATTERNS)
    if results:
        roles["result"].extend(results)

    circumstances, working_action = _extract_patterns(working_action, _CIRCUMSTANCE_PATTERNS)
    if circumstances:
        roles["circumstance"].extend(circumstances)

    cond_text = conditions or ""
    if cond_text:
        cond_exceptions, cond_text = _extract_patterns(cond_text, _EXCEPTION_PATTERNS)
        if cond_exceptions:
            roles["exception"].extend(cond_exceptions)

        for part in re.split(r"\b(?:and|or|;|,)\b", cond_text):
            fragment = _clean_fragment(part)
            if fragment:
                roles["circumstance"].append(fragment)

    if scope:
        fragment = _clean_fragment(scope)
        if fragment:
            roles["circumstance"].append(fragment)

    conduct = _clean_fragment(working_action)
    if conduct:
        roles["conduct"].append(conduct)

    for role, fragments in list(roles.items()):
        seen: set[str] = set()
        unique: List[str] = []
        for fragment in fragments:
            key = fragment.lower()
            if key not in seen and fragment:
                seen.add(key)
                unique.append(fragment)
        if unique:
            roles[role] = unique
        else:
            roles.pop(role, None)

    return dict(roles)


def extract_rules(text: str) -> List[Rule]:
    """Extract rules from a provision text using regex heuristics."""

    rules: List[Rule] = []
    for sent in _split_sentences(text):
        match = None
        pattern_used = None
        for pattern in _PATTERNS:
            match = pattern.match(sent)
            if match:
                pattern_used = pattern
                break
        if not match or not pattern_used:
            continue

        if pattern_used is _OFFENCE_PATTERN:
            actor = match.group("actor").strip()
            modality = f"{match.group('modality').strip()} {match.group('offence').strip()}".lower()
            rest = f"{match.group('trigger').strip()} {match.group('rest').strip()}"
        else:
            actor = match.group("actor").strip()
            modality = match.group("modality").lower()
            rest = match.group("rest").strip()

        conditions = None
        scope = None
        action = rest

        cond_match = re.search(r"\b(if|when|unless)\b(.*)", rest, re.IGNORECASE)
        if cond_match and cond_match.start() > 0:
            action = rest[: cond_match.start()].strip()
            conditions = cond_match.group(0).strip()

        scope_match = re.search(r"\b(within|under)\b(.*)", action, re.IGNORECASE)
        if scope_match:
            scope = scope_match.group(0).strip()
            action = action[: scope_match.start()].strip()

        elements = _classify_fragments(action, conditions, scope)

        party, role, who_text = derive_party_metadata(actor, modality)

        rules.append(
            Rule(
                actor=actor,
                modality=modality,
                action=action.strip(),
                conditions=conditions,
                scope=scope,
                elements=elements,
                party=party,
                role=role,
                who_text=who_text,
            )
        )
    return rules
