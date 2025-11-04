"""Rule extraction utilities."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from src.nlp.taxonomy import Modality

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
    """Split ``text`` into sentences while respecting parentheses."""

    sentences: List[str] = []
    buffer: List[str] = []
    depth = 0

    def flush() -> None:
        candidate = "".join(buffer).strip()
        if candidate:
            sentences.append(candidate)

    for char in text:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1

        if char in ".;" and depth == 0:
            flush()
            buffer = []
            continue

        if char == "\n" and depth == 0:
            flush()
            buffer = []
            continue

        buffer.append(" " if char == "\n" else char)

    flush()
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


def _normalise_condition_text(text: str) -> str:
    """Return a cleaned representation of a conditional clause."""

    fragment = _clean_fragment(text)
    fragment = re.sub(r"\bthen$", "", fragment, flags=re.IGNORECASE)
    return fragment.strip()


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
    cond_text = _normalise_condition_text(cond_text) if cond_text else ""
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
        sentence = sent.strip()
        if not sentence:
            continue

        condition_parts: List[str] = []
        working_sentence = sentence
        match: re.Match[str] | None = None
        pattern_used: re.Pattern[str] | None = None

        if re.match(r"^(if|when|where|unless)\b", working_sentence, re.IGNORECASE):
            prefix_positions = [0]
            prefix_positions.extend(
                match_obj.end()
                for match_obj in re.finditer(r"[\s,;:]+", working_sentence)
            )

            leading_match: tuple[
                int,
                int,
                str,
                str,
                re.Match[str],
                re.Pattern[str],
            ] | None = None

            for pos in prefix_positions:
                segment = working_sentence[pos:]
                stripped_segment = segment.lstrip()
                consumed = len(segment) - len(stripped_segment)
                candidate = stripped_segment
                if not candidate:
                    continue

                prefix_end = pos + consumed
                prefix_text = working_sentence[:prefix_end]
                normalised_prefix = _normalise_condition_text(prefix_text)
                if not normalised_prefix or normalised_prefix.lower() in {"if", "when", "where", "unless"}:
                    continue

                prefix_trimmed = prefix_text.rstrip()
                prefix_has_delimiter = bool(prefix_trimmed and prefix_trimmed[-1] in ",;:")

                for pattern in _PATTERNS:
                    potential_match = pattern.match(candidate)
                    if not potential_match:
                        continue

                    actor_candidate = potential_match.group("actor").strip()
                    if re.match(r"^(if|when|where|unless)\b", actor_candidate, re.IGNORECASE):
                        continue

                    actor_lower = actor_candidate.lower()
                    actor_starts_with_determiner = actor_lower.startswith(
                        (
                            "the ",
                            "a ",
                            "an ",
                            "any ",
                            "each ",
                            "every ",
                            "no ",
                            "all ",
                        )
                    )
                    actor_starts_upper = bool(actor_candidate and actor_candidate[0].isupper())

                    score = 0 if prefix_has_delimiter else 1 if (
                        actor_starts_with_determiner or actor_starts_upper
                    ) else 2

                    candidate_info = (
                        score,
                        prefix_end,
                        normalised_prefix,
                        candidate,
                        potential_match,
                        pattern,
                    )
                    if not leading_match or (score, prefix_end) < leading_match[:2]:
                        leading_match = candidate_info
                    break

            if not leading_match:
                continue

            _, _, best_prefix, best_candidate, best_match, best_pattern = leading_match

            condition_parts.append(best_prefix)
            working_sentence = best_candidate
            match = best_match
            pattern_used = best_pattern
        else:
            for pattern in _PATTERNS:
                potential_match = pattern.match(working_sentence)
                if potential_match:
                    match = potential_match
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
            modality_text = match.group("modality").lower()
            modality_enum = Modality.normalise(modality_text)
            modality = modality_enum.value if modality_enum else modality_text
            rest = match.group("rest").strip()

        conditions = None
        scope = None
        action = rest

        cond_match = re.search(r"\b(if|when|unless)\b(.*)", rest, re.IGNORECASE)
        if cond_match and cond_match.start() > 0:
            action = rest[: cond_match.start()].strip()
            conditions = _normalise_condition_text(cond_match.group(0))

        if condition_parts:
            if conditions:
                condition_parts.append(conditions)
            conditions = "; ".join(part for part in condition_parts if part)
        elif conditions:
            conditions = _normalise_condition_text(conditions)

        if conditions == "":
            conditions = None

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
